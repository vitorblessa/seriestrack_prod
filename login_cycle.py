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
NAV_TIMEOUT_MS = 45_000
LOGIN_WAIT_MS = 90_000  # tempo máximo esperando o servidor aceitar o login
MAX_ATTEMPTS = 2  # tenta o ciclo de novo se o site estiver lento/instável

# Textos possíveis do botão de sair (pt/en)
LOGOUT_TEXT = re.compile(r"^\s*(sair|logout|log out|sign out|desconectar)\s*$", re.I)
# Menus que costumam esconder o "Sair" (perfil, conta, configurações)
MENU_TEXT = re.compile(r"(perfil|conta|configura|settings|account|profile|menu)", re.I)


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def _settle(page, timeout_ms: int = 10_000) -> None:
    """Espera a rede acalmar, mas sem falhar se ela nunca ficar 100% ociosa."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PWTimeout:
        pass


def _visible_error_text(page) -> str:
    """Tenta ler a mensagem de erro que o site mostrou no formulário."""
    try:
        return page.evaluate("""() => {
            const sel = '[role=alert], [aria-live], .error, [class*="error" i], '
                      + '[class*="toast" i], [class*="alert" i], [class*="message" i]';
            const txt = [...document.querySelectorAll(sel)]
                .filter(e => e.offsetParent !== null)
                .map(e => (e.innerText || '').trim())
                .filter(Boolean);
            return [...new Set(txt)].join(' | ').slice(0, 300);
        }""")
    except Exception:  # noqa: BLE001
        return ""


def do_login(page, email: str, password: str) -> None:
    log("Abrindo página de login…")
    # 'domcontentloaded' em vez de 'networkidle': o app pode ficar com requisições
    # abertas (API acordando, analytics) e o networkidle nunca chega.
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)

    email_input = page.locator(
        'input[type="email"], input[name*="email" i], input[autocomplete="username"]'
    ).first
    pwd_input = page.locator('input[type="password"]').first

    email_input.wait_for(state="visible", timeout=TIMEOUT_MS)
    _settle(page, 15_000)  # deixa o app React terminar de montar o formulário

    # Preenche digitando de verdade, para o React registrar os valores
    email_input.click()
    email_input.fill("")
    email_input.press_sequentially(email, delay=30)
    pwd_input.click()
    pwd_input.fill("")
    pwd_input.press_sequentially(password, delay=30)

    if email_input.input_value() != email or not pwd_input.input_value():
        raise RuntimeError("Os campos de e-mail/senha não ficaram preenchidos.")

    # Registra as respostas da API durante o login, para diagnóstico
    api_responses = []

    def _on_response(resp):
        if resp.request.method in ("POST", "PUT") and resp.request.resource_type in ("xhr", "fetch"):
            api_responses.append(f"{resp.status} {resp.request.method} {resp.url}")

    page.on("response", _on_response)

    submit = page.locator(
        'button[type="submit"], button:has-text("Entrar"), button:has-text("Login"), '
        'button:has-text("Acessar"), button:has-text("Sign in")'
    ).first
    submit.click()
    log("Formulário enviado, aguardando resposta do servidor…")

    # Sucesso = saiu da tela /login. Espera longa: a API pode estar "acordando".
    try:
        page.wait_for_url(lambda url: "/login" not in url, timeout=LOGIN_WAIT_MS)
    except PWTimeout:
        for r in api_responses:
            log(f"   API: {r}")
        if not api_responses:
            log("   API: nenhuma resposta recebida (servidor lento/fora do ar?)")
        msg = _visible_error_text(page)
        if msg:
            log(f"   Mensagem na tela: {msg}")
        raise RuntimeError("Login não confirmado: ainda na tela de login.")
    finally:
        page.remove_listener("response", _on_response)
    _settle(page)
    log(f"Login OK — página atual: {page.url}")


# Páginas onde o "Sair" costuma ficar, caso não esteja no dashboard
ACCOUNT_PATHS = ["/perfil", "/profile", "/conta", "/account",
                 "/configuracoes", "/settings", "/ajustes"]


def _logout_locator(page):
    """Qualquer elemento visível que pareça 'sair': texto, aria-label, title ou href."""
    return (
        page.get_by_role("button", name=LOGOUT_TEXT)
        .or_(page.get_by_role("link", name=LOGOUT_TEXT))
        .or_(page.get_by_role("menuitem", name=LOGOUT_TEXT))
        .or_(page.get_by_text(LOGOUT_TEXT))
        .or_(page.locator(
            '[aria-label*="sair" i], [aria-label*="logout" i], [aria-label*="sign out" i], '
            '[title*="sair" i], [title*="logout" i], '
            'a[href*="logout" i], a[href*="signout" i], a[href*="sair" i], '
            '[data-testid*="logout" i]'
        ))
    )


def _try_click_visible(page) -> bool:
    loc = _logout_locator(page)
    for i in range(min(loc.count(), 10)):
        el = loc.nth(i)
        try:
            if el.is_visible():
                el.click(timeout=5_000)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _open_menus_and_try(page) -> bool:
    """Abre menus de perfil/conta (inclusive avatares sem texto) e procura o 'Sair'."""
    menus = (
        page.get_by_role("button", name=MENU_TEXT)
        .or_(page.get_by_role("link", name=MENU_TEXT))
        .or_(page.locator(
            'header button, nav button, [aria-haspopup="menu"], [aria-haspopup="true"], '
            'button:has(img), [class*="avatar" i]'
        ))
    )
    for i in range(min(menus.count(), 12)):
        try:
            m = menus.nth(i)
            if not m.is_visible():
                continue
            m.click(timeout=5_000)
            page.wait_for_timeout(800)
            if _try_click_visible(page):
                return True
            page.keyboard.press("Escape")  # fecha o menu antes de tentar o próximo
        except Exception:  # noqa: BLE001
            continue
    return False


def _log_clickables(page) -> None:
    """Lista botões/links visíveis para descobrir o nome do botão de sair."""
    try:
        items = page.evaluate("""() => [...document.querySelectorAll(
                'button, a, [role=button], [role=menuitem]')]
            .filter(e => e.offsetParent !== null)
            .map(e => [e.tagName.toLowerCase(),
                       (e.innerText || '').trim().slice(0, 40),
                       e.getAttribute('aria-label') || '',
                       e.getAttribute('title') || '',
                       e.getAttribute('href') || ''].join(' | '))
            .slice(0, 60)""")
        log(f"Elementos clicáveis em {page.url} (tag | texto | aria-label | title | href):")
        for it in items:
            log(f"   {it}")
    except Exception as e:  # noqa: BLE001
        log(f"Não consegui listar elementos: {e}")


def click_logout(page) -> bool:
    """Procura o botão de sair no dashboard, em menus e nas páginas de conta."""
    page.wait_for_timeout(1_500)  # dá tempo do app React terminar de renderizar
    if _try_click_visible(page) or _open_menus_and_try(page):
        return True

    _log_clickables(page)  # diagnóstico da tela pós-login

    for path in ACCOUNT_PATHS:
        try:
            page.goto(BASE_URL + path, wait_until="domcontentloaded", timeout=15_000)
            _settle(page, 5_000)
            if "/login" in page.url:  # rota protegida jogou para o login: sessão perdida
                return False
            page.wait_for_timeout(1_000)
            if _try_click_visible(page) or _open_menus_and_try(page):
                log(f"Botão 'Sair' encontrado em {path}")
                return True
        except Exception:  # noqa: BLE001
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
        try:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                context = browser.new_context(locale="pt-BR")
                page = context.new_page()
                try:
                    do_login(page, email, password)
                    do_logout(page, context)
                    log("Ciclo concluído com sucesso.")
                    return 0
                except Exception as e:  # noqa: BLE001
                    log(f"FALHA na tentativa {attempt}/{MAX_ATTEMPTS}: {e}")
                    try:
                        page.screenshot(path="erro.png", full_page=True)
                        log("Screenshot salvo em erro.png")
                    except Exception:  # noqa: BLE001
                        pass
                    if attempt < MAX_ATTEMPTS:
                        log("Aguardando 10s para tentar de novo…")
                        page.wait_for_timeout(10_000)
                finally:
                    context.close()
            return 1
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main())
