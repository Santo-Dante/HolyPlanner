"""Ponto de entrada desktop. Execute com python app.py."""

from pathlib import Path
from threading import RLock
import sys
from holy_planner.backend import Api


class InvestmentWindow:
    """Janela de consulta remota sem expor a API ou os dados do planner."""
    def __init__(self, webview):
        self._webview = webview
        self._window = None
        self._lock = RLock()
        self._closing = False

    def __call__(self, url):
        with self._lock:
            if self._closing:
                raise RuntimeError('O aplicativo está fechando.')
            if self._window is None:
                window = self._webview.create_window(
                    'Investidor10 | Holy Planner', url, js_api=None,
                    width=1280, height=860, min_size=(420, 480),
                    background_color='#0e1417', text_select=True, zoomable=True,
                )
                self._window = window

                def clear_window():
                    with self._lock:
                        if self._window is window:
                            self._window = None

                window.events.closed += clear_window
            else:
                self._window.show()
                self._window.restore()
                self._window.load_url(url)

    def close(self):
        with self._lock:
            self._closing = True
            window, self._window = self._window, None
        if window is not None:
            window.destroy()


def main():
    if '--web' in sys.argv:
        sys.argv.remove('--web')
        if getattr(sys, 'frozen', False) and sys.platform == 'win32':
            import ctypes
            ctypes.windll.kernel32.AllocConsole()
            sys.stdout = open('CONOUT$', 'w', encoding='utf-8')
            sys.stderr = open('CONOUT$', 'w', encoding='utf-8')
            sys.stdin = open('CONIN$', 'r', encoding='utf-8')
        from holy_planner.web_app import main as web_main
        return web_main()
    import argparse
    parser = argparse.ArgumentParser(description='Holy Planner 5.0')
    parser.add_argument('--database', type=Path, help='Banco alternativo para testes ou outro perfil')
    parser.add_argument('--self-test', type=Path, help='Gravar diagnóstico da versão empacotada')
    options = parser.parse_args()
    try:
        import webview
    except ImportError as exc:
        raise SystemExit("Dependencias ausentes. Execute instalar_windows.bat primeiro.") from exc

    frontend = Path(__file__).resolve().parent / "frontend" / "index.html"
    if options.self_test:
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            api = Api(Path(folder) / 'self-test.db')
            task = api.save('tasks', {'title': 'Verificação do aplicativo'})
            from datetime import date
            workout = api.save_workout(dict(title='Verificação de treino',day=date.today().isoformat(),
                                           exercises=[dict(name='Teste',sets=[dict(weight=10,reps=12)])]))
            assets = all((frontend.parent / f).is_file() for f in ('workouts.js','workouts.css','planning.js','life.js','life.css'))
            details = {'ok': frontend.is_file() and task['ok'] and workout['ok'] and assets, 'frontend': frontend.is_file(),
                       'workouts': api.workouts_snapshot()['summary'], 'workout_assets': assets,
                       'snapshot': len(api.snapshot()['tasks']), 'productivity': api.productivity_snapshot()['goals'],
                       'webview': webview.__name__}
        options.self_test.write_text(json.dumps(details), encoding='utf-8')
        return
    investment_viewer = InvestmentWindow(webview)
    window = webview.create_window(
        "Holy Planner 5.0",
        str(frontend),
        js_api=Api(options.database, investment_viewer=investment_viewer),
        width=1440,
        height=900,
        min_size=(360, 480),
        background_color="#14161c",
    )
    window.events.closed += investment_viewer.close
    webview.start(debug=False)


if __name__ == "__main__":
    main()
