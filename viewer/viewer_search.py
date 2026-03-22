"""検索クエリ処理ユーティリティ"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


class QuerySyntaxError(ValueError):
    """検索クエリの構文エラー"""


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


@dataclass(frozen=True)
class _Term:
    value: str


@dataclass(frozen=True)
class _Phrase:
    value: str


@dataclass(frozen=True)
class _Not:
    expr: object


@dataclass(frozen=True)
class _And:
    left: object
    right: object


@dataclass(frozen=True)
class _Or:
    left: object
    right: object


@dataclass(frozen=True)
class ParsedQuery:
    matcher: Callable[[str], bool]
    positive_terms: list[str]


_PRIMARY_START_TOKENS = {"WORD", "PHRASE", "NOT", "MINUS", "LPAREN"}


def _tokenize(query: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    length = len(query)
    while i < length:
        ch = query[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "(":
            tokens.append(_Token("LPAREN", ch))
            i += 1
            continue
        if ch == ")":
            tokens.append(_Token("RPAREN", ch))
            i += 1
            continue
        if ch == "-":
            tokens.append(_Token("MINUS", ch))
            i += 1
            continue
        if ch == '"':
            end = query.find('"', i + 1)
            if end == -1:
                raise QuerySyntaxError("閉じていない引用符があります。")
            phrase = query[i + 1:end]
            if not phrase:
                raise QuerySyntaxError('空のフレーズ "" は検索できません。')
            tokens.append(_Token("PHRASE", phrase))
            i = end + 1
            continue

        start = i
        while i < length and (not query[i].isspace()) and query[i] not in "()":
            i += 1
        word = query[start:i]
        upper = word.upper()
        if upper == "AND":
            kind = "AND"
        elif upper == "OR":
            kind = "OR"
        elif upper == "NOT":
            kind = "NOT"
        else:
            kind = "WORD"
        tokens.append(_Token(kind, word))
    return tokens


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self._tokens = tokens
        self._pos = 0

    def parse(self):
        if not self._tokens:
            raise QuerySyntaxError("検索語を入力してください。")
        expr = self._parse_or()
        token = self._peek()
        if token is not None:
            raise QuerySyntaxError(
                f"解釈できないトークンがあります: {token.value}"
            )
        return expr

    def _peek(self) -> _Token | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _consume(self, expected_kind: str | None = None) -> _Token:
        token = self._peek()
        if token is None:
            raise QuerySyntaxError("検索式が途中で終わっています。")
        if expected_kind is not None and token.kind != expected_kind:
            raise QuerySyntaxError(f"'{token.value}' の位置の構文が不正です。")
        self._pos += 1
        return token

    def _parse_or(self):
        left = self._parse_and()
        while True:
            token = self._peek()
            if token is None or token.kind != "OR":
                return left
            self._consume("OR")
            if self._peek() is None:
                raise QuerySyntaxError("OR の右側に検索語が必要です。")
            right = self._parse_and()
            left = _Or(left, right)

    def _parse_and(self):
        left = self._parse_unary()
        while True:
            token = self._peek()
            if token is None or token.kind in {"OR", "RPAREN"}:
                return left
            if token.kind == "AND":
                self._consume("AND")
                next_token = self._peek()
                if next_token is None:
                    raise QuerySyntaxError("AND の右側に検索語が必要です。")
                if next_token.kind not in _PRIMARY_START_TOKENS:
                    raise QuerySyntaxError(
                        f"AND の右側に検索語が必要です: {next_token.value}"
                    )
            elif token.kind not in _PRIMARY_START_TOKENS:
                raise QuerySyntaxError(f"'{token.value}' の位置の構文が不正です。")
            right = self._parse_unary()
            left = _And(left, right)

    def _parse_unary(self):
        token = self._peek()
        if token is None:
            raise QuerySyntaxError("検索式が途中で終わっています。")
        if token.kind in {"NOT", "MINUS"}:
            self._consume()
            next_token = self._peek()
            if next_token is None or next_token.kind not in _PRIMARY_START_TOKENS:
                raise QuerySyntaxError(f"{token.value} の後ろに検索語が必要です。")
            return _Not(self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self):
        token = self._peek()
        if token is None:
            raise QuerySyntaxError("検索式が途中で終わっています。")
        if token.kind == "WORD":
            return _Term(self._consume("WORD").value)
        if token.kind == "PHRASE":
            return _Phrase(self._consume("PHRASE").value)
        if token.kind == "LPAREN":
            self._consume("LPAREN")
            if self._peek() is not None and self._peek().kind == "RPAREN":
                raise QuerySyntaxError("空の括弧 () は使用できません。")
            expr = self._parse_or()
            if self._peek() is None or self._peek().kind != "RPAREN":
                raise QuerySyntaxError("閉じ括弧 ')' が不足しています。")
            self._consume("RPAREN")
            return expr
        if token.kind == "RPAREN":
            raise QuerySyntaxError("対応する開き括弧 '(' がありません。")
        raise QuerySyntaxError(f"検索語が必要な位置に {token.value} があります。")


def _compile_matcher(expr) -> Callable[[str], bool]:
    if isinstance(expr, (_Term, _Phrase)):
        needle = expr.value.lower()
        return lambda text, value=needle: value in text
    if isinstance(expr, _Not):
        inner = _compile_matcher(expr.expr)
        return lambda text, matcher=inner: not matcher(text)
    if isinstance(expr, _And):
        left = _compile_matcher(expr.left)
        right = _compile_matcher(expr.right)
        return lambda text, lhs=left, rhs=right: lhs(text) and rhs(text)
    if isinstance(expr, _Or):
        left = _compile_matcher(expr.left)
        right = _compile_matcher(expr.right)
        return lambda text, lhs=left, rhs=right: lhs(text) or rhs(text)
    raise TypeError(f"Unsupported expression: {expr!r}")


def _collect_positive_terms(expr) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def visit(node, positive: bool = True):
        if isinstance(node, (_Term, _Phrase)):
            normalized = node.value.lower()
            if positive and normalized not in seen:
                seen.add(normalized)
                terms.append(node.value)
            return
        if isinstance(node, _Not):
            visit(node.expr, False)
            return
        if isinstance(node, (_And, _Or)):
            visit(node.left, positive)
            visit(node.right, positive)
            return
        raise TypeError(f"Unsupported expression: {node!r}")

    visit(expr)
    return terms


def parse_query(query: str) -> ParsedQuery:
    """検索クエリを構文解析し、matcher とハイライト語を返す"""
    tokens = _tokenize(query.strip())
    expr = _Parser(tokens).parse()
    return ParsedQuery(
        matcher=_compile_matcher(expr),
        positive_terms=_collect_positive_terms(expr),
    )


def extract_positive_terms(query: str) -> list[str]:
    """検索クエリから肯定語（NOT/- 除外語を除く）を抽出する"""
    return parse_query(query).positive_terms
