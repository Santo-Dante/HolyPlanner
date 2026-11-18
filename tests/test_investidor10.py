"""URLs externas, persistência, invariância do caixa e ciclo da janela de consulta."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock

from app import InvestmentWindow
from holy_planner.backend import Api
from holy_planner.investidor10 import SECTIONS, section_url, wallet_url

WALLET = 'https://investidor10.com.br/wallet/public/123456'


class InvestmentSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'planner.db'
        self.viewer = Mock()
        self.browser = Mock(return_value=True)
        self.api = Api(self.path, self.viewer, self.browser)
        self.assertTrue(self.api.save_investment_source(dict(enabled='1', wallet_url=WALLET, label='Minha carteira'))['ok'])

    def tearDown(self):
        self.temp.cleanup()

    def test_new_install_has_no_wallet_until_user_links_one(self):
        fresh = Api(Path(self.temp.name) / 'fresh.db', self.viewer, self.browser)
        source = fresh.finance_snapshot('2026-01')['investment_source']
        self.assertEqual(source, dict(enabled=False, wallet_url='', label='Minha carteira', configured=False))
        self.assertFalse(fresh.open_investidor10()['ok'])
        self.assertTrue(fresh.save_investment_source(dict(enabled='0', wallet_url='', label='Local'))['ok'])
        self.assertFalse(fresh.save_investment_source(dict(enabled='1', wallet_url='', label='X'))['ok'])
        self.assertTrue(fresh.save_investment_source(dict(enabled='1', wallet_url='987654', label='Minha'))['ok'])
        self.assertEqual(fresh.finance_snapshot('2026-01')['investment_source']['wallet_url'], section_url('987654'))

    def test_linked_source_and_unchanged_finance_values(self):
        before = self.api.finance_snapshot('2026-01')
        self.assertEqual(before['investment_source']['wallet_url'], WALLET)
        self.assertTrue(before['investment_source']['enabled'])
        self.assertTrue(self.api.open_investidor10()['ok'])
        self.assertEqual(before, self.api.finance_snapshot('2026-01'))

    def test_normalize_public_links_without_forwarding_tracking(self):
        self.assertEqual(wallet_url(' 123456 '), WALLET)
        self.assertEqual(wallet_url('https://www.investidor10.com.br/wallet/public/123456/positions?foo=bar#x'), WALLET)

    def test_reject_external_and_malformed_destinations(self):
        for value in [None, 12, True, '', 'javascript:alert(1)', 'file:///a',
                      'http://investidor10.com.br/wallet/public/1',
                      'https://investidor10.com.br.evil.test/wallet/public/1',
                      'https://evil.test@investidor10.com.br/wallet/public/1',
                      'https://investidor10.com.br:443/wallet/public/1',
                      'https://investidor10.com.br/wallet/my-wallet/1',
                      'https://investidor10.com.br/wallet/public/1/../../other',
                      'https://investidor10.com.br/wallet/public/０１２', '0', '1'*21]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                wallet_url(value)

    def test_each_section_uses_the_saved_wallet(self):
        saved = self.api.save_investment_source(dict(enabled='1',wallet_url='2345',label='Outra carteira'))
        self.assertTrue(saved['ok'])
        for section in SECTIONS:
            result = self.api.open_investidor10(section)
            self.assertTrue(result['ok'])
            self.viewer.assert_called_with(section_url('2345',section))
        self.browser.assert_not_called()

    def test_browser_fallback_uses_only_validated_source(self):
        result = self.api.open_investidor10('earnings', True)
        self.assertTrue(result['ok'])
        self.browser.assert_called_once_with(WALLET+'/earnings',new=2)
        self.viewer.assert_not_called()
        self.browser.return_value = False
        self.assertFalse(self.api.open_investidor10(external=True)['ok'])

    def test_failed_open_and_invalid_actions_are_reported(self):
        self.viewer.side_effect = RuntimeError('native failure')
        self.assertFalse(self.api.open_investidor10()['ok'])
        self.viewer.reset_mock()
        for section, external in [('no-such-section', False), ([], False), ('summary','true')]:
            self.assertFalse(self.api.open_investidor10(section,external)['ok'])
        self.viewer.assert_not_called()
        self.assertFalse(Api(self.path).open_investidor10()['ok'])

    def test_change_source_disable_reopen_and_backup_preserve_transactions(self):
        self.api.save_finance_settings({'opening_cash':'1000','opening_invested':'200'})
        self.assertTrue(self.api.save_transaction(dict(title='Saída existente',kind='expense',amount='100',
                day='2026-01-01',category='Moradia',status='paid'))['ok'])
        before = self.api.finance_snapshot('2026-01')
        payload = dict(enabled='0',wallet_url='2345',label='Reserva')
        self.assertTrue(self.api.save_investment_source(payload)['ok'])
        self.assertFalse(self.api.open_investidor10()['ok'])
        after = Api(self.path).finance_snapshot('2026-01')
        self.assertEqual(after['investment_source'],dict(enabled=False,wallet_url=section_url('2345'),label='Reserva',configured=True))
        for key in before:
            if key != 'investment_source':
                self.assertEqual(before[key],after[key],key)
        backup = self.api.backup()
        self.assertTrue(backup['ok'])
        self.assertEqual(Api(backup['path']).finance_snapshot('2026-01'),after)
        payload['enabled'] = '1'
        self.assertTrue(self.api.save_investment_source(payload)['ok'])
        self.assertTrue(self.api.open_investidor10()['ok'])

    def test_invalid_configuration_is_atomic(self):
        before = self.api.finance_snapshot()['investment_source']
        for payload in [None, {}, dict(enabled='yes',wallet_url=WALLET),
                        dict(enabled='1',wallet_url='https://evil.test'),
                        dict(enabled='1',wallet_url=WALLET,label='x'*81)]:
            self.assertFalse(self.api.save_investment_source(payload)['ok'])
            self.assertEqual(self.api.finance_snapshot()['investment_source'],before)

    def test_upgrade_existing_finance_db_keeps_balances(self):
        self.api.save_finance_settings({'opening_cash':'1234,56','opening_invested':'7890'})
        with self.api._database() as db:
            db.write('DROP TABLE investment_source')
        migrated = Api(self.path).finance_snapshot('2026-01')
        self.assertEqual(migrated['cash_cents'],123456)
        self.assertEqual(migrated['invested_cents'],789000)
        self.assertEqual(migrated['investment_source']['wallet_url'],'')
        self.assertFalse(migrated['investment_source']['enabled'])


class InvestmentWindowTests(unittest.TestCase):
    def test_reuse_close_and_reopen_without_local_api(self):
        webview = Mock()
        first, second = MagicMock(), MagicMock()
        for window in (first,second):
            event = window.events.closed
            event.__iadd__.return_value = event
        webview.create_window.side_effect = [first, second]
        viewer = InvestmentWindow(webview)
        viewer(WALLET)
        self.assertIsNone(webview.create_window.call_args.kwargs['js_api'])
        viewer(WALLET+'/positions')
        self.assertEqual(webview.create_window.call_count,1)
        first.show.assert_called_once()
        first.restore.assert_called_once()
        first.load_url.assert_called_once_with(WALLET+'/positions')
        clear = first.events.closed.__iadd__.call_args.args[0]
        clear()
        viewer(WALLET)
        self.assertEqual(webview.create_window.call_count,2)
        viewer.close()
        second.destroy.assert_called_once()
        with self.assertRaises(RuntimeError):
            viewer(WALLET)


if __name__ == '__main__':
    unittest.main()
