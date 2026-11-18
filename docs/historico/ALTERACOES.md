# Análise e melhorias — Holy Planner 3.0

## O que foi encontrado

O projeto já tinha uma divisão clara entre interface, API e SQLite, validação dos registros, acesso serializado ao banco e testes para planner e Google Agenda. Essa estrutura foi mantida.

Foram identificados dois problemas concretos:

1. **Instalação incompleta:** `instalar_windows.bat` exigia `requirements.txt`, mas o RAR não continha esse arquivo. A instalação em um ambiente novo falhava.
2. **Arquivo de backup preso no Windows:** o `with sqlite3.connect(...)` encerra a transação, mas não fecha a conexão. O banco de destino podia continuar aberto, impedindo mover/excluir o backup. O fechamento agora é explícito e há uma regressão que verifica renomear o backup no Windows.

O RAR incluía um ambiente `.venv` específico da máquina original. A entrega usa o código e um manifesto de dependências; o ambiente será recriado pelo instalador. Não foram encontrados registros pessoais ou banco SQLite dentro do RAR.

## O que mudou

- Aba Finanças com visão geral, lançamentos, investimentos e limites mensais por categoria.
- Entradas, saídas, aportes, resgates e rendimentos recebidos, com edição, exclusão e situação previsto/efetivado.
- Saldo disponível acumulado, projeção mensal, capital registrado, movimentos por investimento e gráficos locais.
- Categorias personalizadas, identificação de conta, notas, busca e filtros.
- Exportação CSV com os filtros da lista, vírgula decimal, UTF-8 com BOM e neutralização de textos que poderiam ser interpretados como fórmulas.
- Valores em centavos inteiros e validação no Python; dinheiro nunca é gravado como float.
- Categorias e investimentos reutilizam a grafia existente, inclusive diferenças de caixa em letras acentuadas.
- Atualização aditiva do banco antigo com backup automático anterior à migração.
- Backup completo inclui os novos dados e fecha a conexão de destino.
- Navegação acessível, formulários adaptáveis, estados vazios e mensagens de erro. A área Google Agenda fica oculta na aba Finanças.
- Manifesto de dependências, instruções atualizadas e testes financeiros.

## Verificação

40 testes passaram: 24 regressões existentes e 16 novos testes financeiros. Incluem valores decimais brasileiros, cálculos de caixa e capital, meses e ano bissexto, edição e exclusão, concorrência, previstos/futuros, limites, CSV, migração e backup. Testes foram executados com diretórios temporários na pasta de trabalho e ACLs herdadas, devido às restrições do ambiente de execução.

O Google foi testado com transporte simulado; nenhuma conta real foi conectada. A interface usou o backend Python real e banco separado com dados fictícios. Foram verificados criação de despesa e aporte, edição, efetivação, saldos iniciais, limite excedido, busca, CSV filtrado e cancelamento da confirmação de exclusão. A exclusão efetiva foi coberta pelos testes de backend.

As quatro seções financeiras foram verificadas em 320, 600, 820 e 1440 pixels; as cinco abas originais também foram conferidas em 320 pixels. Nenhuma apresentou rolagem horizontal ou erro JavaScript. A janela nativa pywebview/WebView2 não foi executada nesta validação.

## Limites atuais

O controle é manual, com saldos consolidados. Não conecta bancos, importa extratos, consulta preços de ativos, contabiliza valorização/perdas automaticamente ou executa transações financeiras. Contas identificam os lançamentos, sem saldos individuais. Limites não se repetem automaticamente para outros meses. A restauração de backup continua sendo feita com o programa fechado, substituindo o arquivo do banco.
