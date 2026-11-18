"""Servidor privado do Holy Planner para navegador, PWA e rede local."""
import argparse
import hmac
import json
import mimetypes
import secrets
import socket
import ssl
import time
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .backend import Api
from . import investidor10
FRONTEND = Path(__file__).resolve().parent.parent / 'frontend'
METHODS = {
    'snapshot', 'calendar_month', 'save', 'delete', 'toggle_task', 'toggle_routine',
    'backup', 'google_status', 'google_sync', 'finance_snapshot', 'save_transaction',
    'delete_finance', 'toggle_transaction', 'save_budget', 'save_finance_settings',
    'save_investment_source', 'export_finances', 'productivity_snapshot',
    'save_productivity', 'delete_productivity', 'set_task_status', 'save_focus_session',
    'workouts_snapshot', 'save_workout', 'delete_workout',
    'planning_snapshot', 'save_wealth_record', 'save_scenario', 'set_scenario_visible', 'delete_planning',
    'app_settings', 'save_app_settings', 'reminders', 'review_snapshot', 'save_review', 'schedule_tasks',
    'save_journal', 'delete_journal', 'journal_snapshot', 'delete_transaction', 'copy_budgets', 'import_preview', 'import_commit',
    'save_workout_template', 'delete_workout_template',
}


class PlannerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, api, pairing_code=None):
        self.api = api
        self.pairing_code = pairing_code or secrets.token_urlsafe(12)
        self.sessions = {}
        self.attempts = {}
        self.secure = False
        super().__init__(address, PlannerHandler)


class PlannerHandler(BaseHTTPRequestHandler):
    server_version = 'HolyPlanner/5.0'

    def log_message(self, *args):
        pass  # Não escreve tokens, dados pessoais ou URLs nos logs.

    def reply(self, status, content, content_type='application/json; charset=utf-8', headers=None):
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False).encode('utf-8')
        elif isinstance(content, str):
            content = content.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store' if content_type.startswith('application/json') else 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(content)

    def authenticated(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return False
        token = cookie.get('holy_session')
        return bool(token and self.server.sessions.get(token.value, 0) > time.time())

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/session':
            return self.reply(200, {'authenticated': self.authenticated()})
        # Serve somente arquivos públicos da interface, nunca o banco ou credenciais.
        relative = 'index.html' if path == '/' else path.lstrip('/')
        target = (FRONTEND / relative).resolve()
        if not target.is_relative_to(FRONTEND.resolve()) or not target.is_file():
            return self.reply(404, {'error': 'Arquivo não encontrado.'})
        mime = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        if target.suffix == '.js':
            mime = 'text/javascript'
        content = target.read_bytes()
        if target.name == 'index.html':
            content = content.replace(b'<body>', b'<body data-runtime="web">', 1)
        self.reply(200, content, mime)

    def do_POST(self):
        origin = self.headers.get('Origin')
        # JSON + cabeçalho próprio evitam formulários cross-origin e DNS rebinding.
        if (origin and urlsplit(origin).netloc != self.headers.get('Host')) or self.headers.get('X-Holy-Planner') != '1':
            return self.reply(403, {'ok': False, 'error': 'Origem não autorizada.'})
        if not self.headers.get('Content-Type', '').startswith('application/json'):
            return self.reply(415, {'ok': False, 'error': 'Use JSON.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 3_000_000:
                raise ValueError('Requisição inválida ou muito grande.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Requisição inválida.')
        except (ValueError, UnicodeError):
            return self.reply(400, {'ok': False, 'error': 'Requisição inválida.'})
        if self.path == '/api/login':
            address = self.client_address[0]
            count, until = self.server.attempts.get(address, (0, 0))
            if until < time.time():
                count = 0
            if count >= 10:
                return self.reply(429, {'ok': False, 'error': 'Aguarde um minuto antes de tentar novamente.'})
            code = data.get('code', '')
            if not isinstance(code, str) or not hmac.compare_digest(code.encode(), self.server.pairing_code.encode()):
                self.server.attempts[address] = (count + 1, time.time() + 60)
                return self.reply(401, {'ok': False, 'error': 'Código incorreto. Confira a janela do servidor no computador.'})
            self.server.attempts.pop(address, None)
            self.server.sessions = {key: expiry for key, expiry in self.server.sessions.items() if expiry > time.time()}
            token = secrets.token_urlsafe(32)
            self.server.sessions[token] = time.time() + 30 * 86400
            cookie = f'holy_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000'
            if self.server.secure:
                cookie += '; Secure'
            return self.reply(200, {'ok': True}, headers={'Set-Cookie': cookie})
        if not self.authenticated():
            return self.reply(401, {'ok': False, 'error': 'Conecte este dispositivo com o código do computador.'})
        if self.path != '/api/call':
            return self.reply(404, {'ok': False, 'error': 'Rota desconhecida.'})
        method, args = data.get('method'), data.get('args', [])
        if not isinstance(method, str) or not isinstance(args, list) or len(args) > 5:
            return self.reply(400, {'ok': False, 'error': 'Chamada inválida.'})
        try:
            if method == 'open_investidor10':
                with self.server.api._database() as db:
                    config = investidor10.configuration(db)
                if not config['enabled']:
                    raise ValueError('Configure o link da sua carteira em Finanças → Investimentos.')
                result = {'ok': True, 'url': investidor10.section_url(config['wallet_url'], args[0] if args else 'summary')}
            elif method in ('google_connect', 'google_disconnect'):
                result = {'ok': False, 'error': 'Conecte ou desconecte o Google pela janela do aplicativo no computador.'}
            elif method not in METHODS:
                return self.reply(403, {'ok': False, 'error': 'Método não autorizado.'})
            else:
                result = getattr(self.server.api, method)(*args)
            # Os arquivos criados pelo backend são baixados no dispositivo solicitante.
            if method in ('backup', 'export_finances') and result.get('ok'):
                target = Path(result['path'])
                import base64
                result['download'] = {'name': target.name, 'data': base64.b64encode(target.read_bytes()).decode('ascii')}
            self.reply(200, result)
        except (ValueError, TypeError) as exc:
            self.reply(400, {'ok': False, 'error': str(exc)})
        except Exception:
            self.reply(500, {'ok': False, 'error': 'Não foi possível concluir. Tente novamente.'})


def main():
    parser = argparse.ArgumentParser(description='Holy Planner no computador e no celular')
    parser.add_argument('--lan', action='store_true', help='Permitir acesso pela rede local')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--cert', type=Path, help='Certificado HTTPS confiável no celular')
    parser.add_argument('--key', type=Path, help='Chave privada do certificado')
    parser.add_argument('--no-browser', action='store_true')
    options = parser.parse_args()
    if bool(options.cert) != bool(options.key):
        parser.error('Informe --cert e --key juntos.')
    server = PlannerServer(('0.0.0.0' if options.lan else '127.0.0.1', options.port), Api(options.database))
    if options.cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(options.cert, options.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        server.secure = True
    scheme = 'https' if server.secure else 'http'
    local_url = f'{scheme}://localhost:{options.port}'
    print(f'\nHOLY PLANNER 5.0\n\nNo computador: {local_url}\nCódigo de conexão: {server.pairing_code}\n', flush=True)
    if options.lan:
        addresses = sorted({r[4][0] for r in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
        for address in addresses:
            print(f'No celular, na mesma rede Wi-Fi: {scheme}://{address}:{options.port}', flush=True)
        print('Mantenha esta janela aberta. Use apenas uma rede de confiança.', flush=True)
        print('Fora de casa: veja docs/ACESSO_REMOTO.md (Tailscale, sem abrir portas no roteador).\n', flush=True)
    if not options.no_browser:
        webbrowser.open(local_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
