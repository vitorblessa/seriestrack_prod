"""
Ciclo de login/logout no SeriesTrack (https://www.series-track.com).

O site é um app React (SPA), então usamos um navegador headless (Playwright)
em vez de requisições HTTP simples.

Credenciais vêm de variáveis de ambiente — nunca coloque senha no código:
    ST_EMAIL     e-mail da conta
    ST_PASSWORD  senha da conta

Uso local:
    pip install -r requirements.txt
    python -m playwright install --with-deps chromium
    ST_EMAIL=... ST_PASSWORD=... python login_cycle.py
"""

import os
import re
import sys
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL = "https://www.series-track.com"
LOGIN_URL = f"{BASE_URL}/login"
TIMEOUT_MS = 30_000

# Textos possíveis do botão de sair (pt/en)
LOGOUT_TEXT = re.compile(r"^\s*(sair|logout|log out|sign out|desconectar)\s*$", re.I)
# Menus que costumam esconder o "Sair" (perfil, conta, configurações)
MENU_TEXT = re.compile(r"(perfil|conta|configura|settings|account|profile|menu)", re.I)


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def do_login(page, email: str, password: str) -> None:
    log("Abrindo página de login…")
    page.goto(LOGIN_URL, wait_until="networkidle", timeout=TIMEOUT_MS)

    email_input = page.locator(
        'input[type="email"], input[name*="email" i], input[autocomplete="username"]'
    ).first
    pwd_input = page.locator('input[type="password"]').first

    email_input.wait_for(state="visible", timeout=TIMEOUT_MS)
    email_input.fill(email)
    pwd_input.fill(password)

    submit = page.locator(
        'button[type="submit"], button:has-text("Entrar"), button:has-text("Login"), '
        'button:has-text("Acessar"), button:has-text("Sign in")'
    ).first
    submit.click()

    # Sucesso = saiu da tela /login (ou o campo de senha sumiu)
    try:
        page.wait_for_url(lambda url: "/login" not in url, timeout=TIMEOUT_MS)
    except PWTimeout:
        if pwd_input.is_visible():
            raise RuntimeError(
                "Login não confirmado: ainda na tela de login. "
                "Verifique as credenciais ou se surgiu captcha/2FA."
            )
    page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
    log(f"Login OK — página atual: {page.url}")


def click_logout(page) -> bool:
    """Tenta achar e clicar no botão de sair, abrindo menus se preciso."""
    candidates = page.get_by_role("button", name=LOGOUT_TEXT).or_(
        page.get_by_role("link", name=LOGOUT_TEXT)
    ).or_(page.get_by_text(LOGOUT_TEXT))

    if candidates.first.is_visible():
        candidates.first.click()
        return True

    # Abre menus de perfil/conta e procura de novo
    menus = page.get_by_role("button", name=MENU_TEXT).or_(
        page.get_by_role("link", name=MENU_TEXT)
    )
    for i in range(min(menus.count(), 5)):
        try:
            menus.nth(i).click(timeout=5_000)
            page.wait_for_timeout(1_000)
            if candidates.first.is_visible():
                candidates.first.click()
                return True
        except PWTimeout:
            continue
    return False


def do_logout(page, context) -> None:
    log("Fazendo logout…")
    clicked = False
    try:
        clicked = click_logout(page)
    except Exception as e:  # noqa: BLE001
        log(f"Aviso ao procurar botão de sair: {e}")

    if clicked:
        try:
            page.wait_for_url(lambda url: "/login" in url or url.rstrip("/") == BASE_URL,
                              timeout=15_000)
        except PWTimeout:
            pass
        log("Logout via botão 'Sair' concluído.")
    else:
        log("Botão 'Sair' não encontrado — encerrando sessão limpando cookies/storage.")

    # Garante sessão zerada para o próximo ciclo, de qualquer forma
    try:
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
    except Exception:  # noqa: BLE001
        pass
    context.clear_cookies()
    log("Sessão limpa — pronto para o próximo ciclo.")


def main() -> int:
    email = os.environ.get("ST_EMAIL")
    password = os.environ.get("ST_PASSWORD")
    if not email or not password:
        log("ERRO: defina ST_EMAIL e ST_PASSWORD.")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="pt-BR")
        page = context.new_page()
        try:
            do_login(page, email, password)
            do_logout(page, context)
            log("Ciclo concluído com sucesso.")
            return 0
        except Exception as e:  # noqa: BLE001
            log(f"FALHA no ciclo: {e}")
            try:
                page.screenshot(path="erro.png", full_page=True)
                log("Screenshot salvo em erro.png")
            except Exception:  # noqa: BLE001
                pass
            return 1
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main())
