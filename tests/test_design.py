"""O progresso semanal do novo painel reflete as ocorrências reais."""
import unittest
from datetime import date, timedelta
from tests import test_backend
class DashboardWeekTests(unittest.TestCase):
    setUp = test_backend.ApiTests.setUp
    tearDown = test_backend.ApiTests.tearDown

    def test_week_has_seven_days_and_completion_updates(self):
        today=date.today()
        item=self.api.save('routines',{'title':'Leitura','days':list(range(7))})['id']
        week=self.api.snapshot()['routine_week']
        self.assertEqual(len(week),7)
        self.assertEqual(week[0]['day'],(today-timedelta(days=today.weekday())).isoformat())
        self.assertEqual(week[today.weekday()]['total'],1)
        self.assertEqual(week[today.weekday()]['done'],0)
        self.api.toggle_routine(item,today.isoformat())
        self.assertEqual(self.api.snapshot()['routine_week'][today.weekday()]['done'],1)
        self.api.toggle_routine(item,today.isoformat())
        self.assertEqual(self.api.snapshot()['routine_week'][today.weekday()]['done'],0)

    def test_week_respects_creation_and_selected_weekdays(self):
        today=date.today()
        self.api.save('routines',{'title':'Hoje','days':[today.weekday()]})
        week=self.api.snapshot()['routine_week']
        self.assertTrue(all(day['total']==(i==today.weekday()) for i,day in enumerate(week)))
        self.assertTrue(all(day['done']==0 for day in week))


if __name__ == '__main__': unittest.main()
