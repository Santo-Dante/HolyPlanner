"""Prévia isolada: nunca lê ou modifica o banco pessoal do usuário."""
import sys
from pathlib import Path
from datetime import date, timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from holy_planner.backend import Api
from holy_planner.web_app import PlannerServer

folder=Path(__file__).resolve().parents[1]/'.test-data'
folder.mkdir(exist_ok=True)
api=Api(folder/'preview.db')
if not api.snapshot()['tasks']:
    today=date.today().isoformat()
    project=api.save('projects',dict(title='Meu desenvolvimento',description='Aprender com intenção, um pouco todos os dias.'))['id']
    for title,priority,hour,estimate,offset,status in [
        ('Organizar as prioridades da semana','Alta','09:00',20,0,'A fazer'),
        ('Ler um capítulo do livro','Média','18:00',30,0,'Em andamento'),
        ('Revisar o planejamento financeiro','Média','14:00',25,0,'A fazer'),
        ('Preparar o próximo projeto','Baixa','10:00',60,1,'A fazer'),
        ('Uma caminhada para renovar as ideias','Baixa','07:00',30,0,'Concluído')]:
        api.save('tasks',dict(title=title,priority=priority,scheduled_time=hour,estimate_minutes=estimate,
                             due=(date.today()+timedelta(days=offset)).isoformat(),status=status,project_id=project))
    for title in ('Beber água','Ler por 20 minutos','Movimentar o corpo'):
        api.save('routines',dict(title=title,days=list(range(7))))
    api.toggle_routine(api.snapshot()['routines'][0]['id'],today)
    api.save_productivity('goals',dict(title='Ler 12 livros este ano',target=12,current=5,unit='livros',due=f'{date.today().year}-12-31'))
    api.save_productivity('goals',dict(title='Cuidar de mim com constância',target=30,current=18,unit='treinos'))
    api.save_productivity('notes',dict(title='Um lembrete para dias cheios',body='Não preciso resolver tudo hoje.\n\nUm passo com intenção já é um bom começo.',pinned=1))
    api.save_focus_session(dict(id='preview-session-01',title='Leitura da manhã',minutes=25,day=today))
if not api.workouts_snapshot()['sessions']:
    for i, offset in enumerate((24,18,12,6,0)):
        api.save_workout(dict(title='Treino A · Peito e tríceps',day=(date.today()-timedelta(days=offset)).isoformat(),
            notes='Carga total da barra. Movimento controlado e boa amplitude.',
            exercises=[dict(name='Supino reto',sets=[dict(weight=30+i*2.5,reps=12),dict(weight=30+i*2.5,reps=10),dict(weight=30+i*2.5,reps=10)]),
                       dict(name='Tríceps na polia',sets=[dict(weight=15+i,reps=12)]*3)],
            cardio=[dict(name='Corrida na esteira',minutes=30,distance_km=4+i*.25)]))
if not api.planning_snapshot()['scenarios']:
    api.save_finance_settings(dict(opening_cash='28000', opening_invested='15000'))
    first = date.today().replace(day=1)
    wealth = 15000.0
    for back in range(18, 0, -1):
        month = (first.year * 12 + first.month - 1) - back
        day = date(month // 12, month % 12 + 1, 5)
        amount = 800 + (back % 3) * 150
        api.save_transaction(dict(title='Aporte mensal', kind='investment', amount=str(amount), day=day.isoformat(),
                                  category='Investimentos', asset='Tesouro e ações', status='paid'))
        wealth = wealth * 1.009 + amount + (240 if back % 5 == 0 else -120 if back % 7 == 0 else 0)
        api.save_wealth_record(dict(day=date(month // 12, month % 12 + 1, 28).isoformat(), amount=f'{wealth:.2f}', notes='Investidor10'))
    for name, rate, monthly, events, target in [
        ('Moderado', '10', '1000', [dict(title='13º salário', kind='deposit', month=f'{first.year}-12', amount='3000', yearly=True)], '250000'),
        ('Conservador', '8', '800', [], ''),
        ('Arrojado com viagem', '12', '1200', [dict(title='Viagem', kind='withdrawal', month=f'{first.year + 3}-07', amount='25000', yearly=False)], '')]:
        api.save_scenario({**dict(name=name, start_mode='snapshot', monthly=monthly, annual_rate=rate, inflation='4',
                               years=10, target=target, notes='', events=events), 'raise': '3'})
if not api.journal_snapshot()['entries']:
    for offset in range(1, 21):
        day = date.today() - timedelta(days=offset)
        trained = offset % 3 != 0
        if trained and offset % 2 == 0:
            api.save_workout(dict(title='Treino B · Costas', day=day.isoformat(),
                exercises=[dict(name='Remada curvada', sets=[dict(weight=40, reps=10)] * 3)]))
        api.save_journal(dict(day=day.isoformat(), mood=4 if offset % 2 == 0 else 3, energy=4 if offset % 4 else 2,
                              sleep='7,5' if offset % 3 else '6', note='Dia produtivo.' if offset % 2 == 0 else ''))
    sessions = api.workouts_snapshot()['sessions']
    first = next(s for s in sessions if s['title'].startswith('Treino A'))
    api.save_workout_template(dict(name='Treino A · Peito e tríceps', exercises=[dict(name=e['name'], sets=len(e['sets'])) for e in first['exercises']],
                                   cardio=[dict(name='Corrida na esteira', minutes=20)]))
    api.save('routines', dict(title='Treinar', days=[0, 1, 2, 3, 4], auto_workout='1'))
    api.save_productivity('goals', dict(title='Treinar 12 vezes no mês', target=12, unit='treinos', source='workouts', period='month'))
    api.save_productivity('goals', dict(title='Chegar a R$ 50 mil investidos', target=50000, unit='reais', source='wealth'))
    soon = (date.today() + timedelta(days=1)).isoformat()
    api.save_transaction(dict(title='Conta de luz', kind='expense', amount='182,40', day=soon, category='Moradia', status='pending'))
    api.save_transaction(dict(title='Salário', kind='income', amount='6500', day=date.today().replace(day=1).isoformat(), category='Salário', status='paid'))
    api.save('tasks', dict(title='Organizar documentos do carro', priority='Alta'))
    api.save('tasks', dict(title='Pesquisar curso de inglês'))
print('Preview: http://localhost:8766 | code: preview-only',flush=True)
PlannerServer(('127.0.0.1',8766),api,'preview-only').serve_forever()
