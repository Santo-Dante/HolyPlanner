# Manual de uso

Guia detalhado das funções que vêm desde as versões 3.x (finanças, planner, Google Agenda, backups). Para a visão geral do projeto, veja o [README](../README.md). Novidades recentes: [ROTINA.md](ROTINA.md) (5.0), [PLANEJAMENTO.md](PLANEJAMENTO.md) (4.2) e [TREINOS.md](TREINOS.md) (4.1). Executável, celular e PWA: [APP.md](APP.md).

Seu planner pessoal com projetos, tarefas, calendário, rotinas e controle financeiro. Interface em português, tema cinza escuro e verde-água e dados locais em SQLite. O planner e o caixa funcionam offline depois da instalação. O Google Agenda é opcional; a consulta da carteira no Investidor10 precisa de internet.

Em **Finanças → Investimentos** você pode vincular a sua carteira pública do Investidor10. Veja [INVESTIDOR10.md](INVESTIDOR10.md) para o funcionamento e os limites deste acesso.

## Começar no Windows

1. Extraia o ZIP em uma pasta de sua preferência. Use a pasta inteira.
2. Com Python 3.10 ou superior instalado, execute `scripts\instalar_windows.bat`. A instalação das dependências exige internet.
3. Execute `scripts\iniciar_windows.bat` para abrir o programa.
4. Em **Finanças → Saldos iniciais**, informe o saldo disponível anterior ao primeiro lançamento que você pretende registrar. O capital investido inicial é usado somente pelo controle local de movimentos.
5. Em **Finanças → Investimentos**, clique em **Abrir carteira no aplicativo** para consultar o Investidor10. Use **Abrir no navegador** para acessar sua conta e editar os investimentos.

O código-fonte e a distribuição executável estão disponíveis. Para a versão pronta, abra `dist\Holy Planner\Holy Planner.exe` e mantenha a pasta `_internal` ao lado. Para executar pelo código, não copie ambientes `.venv` de outro computador: o instalador cria um ambiente local. A janela usa pywebview e Microsoft Edge WebView2. Abrir `frontend/index.html` sozinho não conecta ao banco.

Alternativa no terminal, na pasta do projeto:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

## Finanças

**Visão geral:** saldo disponível acumulado até o fim do mês escolhido, projeção após os previstos daquele mês, entradas, despesas, aportes, fluxo do mês, gráficos de seis meses e despesas por categoria.

**Lançamentos:** crie, edite e exclua entradas, saídas, aportes, resgates e rendimentos recebidos. Informe descrição, valor, data, categoria, conta/instituição opcional e notas. A conta é uma identificação do lançamento; os saldos são consolidados, sem conciliação bancária ou transferências entre contas. Você pode criar categorias digitando seu nome.

- **Efetivado:** já aconteceu; entra nos saldos e nos resumos.
- **Previsto:** ainda não aconteceu; aparece apenas na projeção. Clique no círculo do lançamento para efetivar ou devolver a previsto.
- Lançamentos futuros precisam ficar como previstos. Se pagou antecipadamente, edite a data para a data real antes de efetivar.
- A busca procura descrição, categoria, conta, investimento e notas. Combine com os filtros de tipo, situação e categoria.
- Os filtros da lista não alteram os indicadores da visão geral.

**Investimentos:** abra sua carteira na página oficial do Investidor10, em uma janela do aplicativo ou no navegador. Há atalhos para posições, proventos, patrimônio, rentabilidade e lançamentos. O link já está configurado e pode ser alterado em **Configurar carteira**. Este acesso não importa dados automaticamente para o Holy Planner.

Em **Movimentos de investimentos no saldo local**, acompanhe os movimentos por ativo/investimento. Aportes diminuem o disponível e aumentam o capital registrado; resgates fazem o movimento contrário. Registre no resgate o principal devolvido e registre ganhos recebidos em **Rendimento recebido**. Para reinvestir um rendimento, lance o rendimento e um aporte do mesmo valor. Perdas, taxas, valorização não realizada e cotações não são calculadas automaticamente. O capital registrado é um controle dos valores informados, não o valor de mercado da carteira.

O capital inicial investido fica separado como **Capital anterior ao controle**. Os cartões de cada ativo mostram os aportes líquidos e rendimentos registrados depois do início do controle. Confira saldos e histórico se houver resgates maiores que os aportes registrados.

**Limites do mês:** defina um limite de despesas por categoria para o mês selecionado. O programa mostra gasto efetivado, previsto, valor restante e excesso. Aportes não contam como despesas. Salvar novamente a mesma categoria e mês atualiza o limite; meses diferentes têm limites independentes.

**Exportar CSV:** salva um arquivo compatível com Excel/LibreOffice em `exports` junto ao banco e mostra o caminho. Na seção Lançamentos, exporta somente os registros visíveis com os filtros atuais. Nas outras seções, exporta todos os lançamentos do mês. Usa ponto e vírgula, UTF-8 com BOM e vírgula decimal. Não importa extratos ou CSV nesta versão.

Os valores são gravados como centavos inteiros. Você pode digitar `1234,56`, `1.234,56` ou `1234.56`. Valores precisam ser positivos, com até duas casas decimais. O saldo disponível inicial aceita valor negativo para representar uma dívida existente.

Os saldos iniciais se aplicam a todo o histórico e representam o que existia antes do primeiro lançamento registrado. Não repita nos saldos iniciais valores já incluídos nos lançamentos.

## Planner e Google Agenda

- **Meu dia:** tarefas de hoje e atrasadas, rotinas programadas e eventos Google em cache.
- **Projetos:** descrição, prazo e progresso das tarefas. Excluir um projeto mantém suas tarefas sem projeto.
- **Tarefas:** projeto opcional, prioridade, prazo, status, notas, busca e filtro. Tarefas sem prazo ficam nesta aba.
- **Calendário:** navegação mensal, seleção do dia e agenda. Nova tarefa recebe o dia selecionado.
- **Rotinas:** dias da semana e conclusão independente por ocorrência. Não é possível concluir uma rotina futura. Editar os dias redefine a programação nas consultas passadas, preservando os registros de conclusão existentes.
- **Google Agenda:** tarefas e projetos com prazo podem ser sincronizados. Veja `GOOGLE_AGENDA.md`. Rotinas e finanças ficam locais; nenhum lançamento financeiro é enviado ao Google.

## Dados antigos, backups e restauração

O banco continua em `%LOCALAPPDATA%\HolyPlanner\planner.db` no Windows. Trocar a pasta de código não altera seus registros. O RAR recebido não continha um banco de dados.

Ao abrir um banco antigo, a versão 3.0 cria um backup `antes-financas-...db` em `HolyPlanner\backups` antes de acrescentar as tabelas financeiras. As tabelas existentes e os registros do planner são preservados. Se o backup falhar, a atualização é interrompida.

**Salvar backup** faz uma cópia completa, incluindo finanças, limites, saldos iniciais, link e preferência da carteira, planner e cache da agenda. Os arquivos ficam em `HolyPlanner\backups`. Os dados hospedados no Investidor10 continuam na plataforma e não são copiados pelo backup do Holy Planner.

Para restaurar, feche o programa, guarde uma cópia do banco atual e substitua `planner.db` pelo backup desejado. Abra novamente com esta versão ou uma versão posterior. Backups da versão 3.0 devem ser restaurados com o código da versão 3.0 ou posterior.

## Arquivos e validação

| Arquivo | Função |
|---|---|
| `app.py` | Entrada: janela desktop e servidor web (`--web`) |
| `holy_planner/backend.py` | API e validação dos formulários |
| `holy_planner/database.py` | Persistência do planner, migração e backup |
| `holy_planner/finance.py` | Cálculos financeiros, centavos, tabelas e CSV |
| `holy_planner/finance_import.py` | Importação de extratos OFX/CSV e sugestão de categorias |
| `holy_planner/investidor10.py` | Configuração e validação do link público da carteira |
| `holy_planner/investment_plan.py` | Planejar investimentos |
| `holy_planner/life.py` | Lembretes, revisão semanal, diário e metas automáticas |
| `holy_planner/google_calendar.py` | Integração opcional com Google Agenda |
| `holy_planner/web_app.py` | Servidor para navegador e celular |
| `frontend/` | Interface (HTML, CSS e JavaScript sem build) |
| `tests/` | Testes Python e JavaScript |

Execute os testes com as dependências instaladas:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Na revisão financeira 3.0, foram executados 40 testes de backend, persistência, finanças, migração e Google com transporte simulado. A interface foi verificada em Chromium com uma ponte HTTP para o backend real e banco fictício separado, incluindo formulários, edição, efetivação, busca e exportação. As quatro seções financeiras foram verificadas em 320, 600, 820 e 1440 pixels de largura, sem conteúdo fora da janela. O JavaScript passou na verificação de sintaxe. A janela nativa pywebview/WebView2 não foi executada nesta validação.

Veja `ALTERACOES.md` para a análise e as correções desta entrega.
