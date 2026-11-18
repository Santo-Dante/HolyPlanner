# Holy Planner 3.1 — novo design

Interface redesenhada a partir da imagem fornecida, usando os mesmos dados e funções da versão 3.0.

- Cabeçalho com marca horizontal, navegação das seis abas, busca na aba atual e configurações.
- Paleta de cinza escuro e verde-água, cartões com bordas suaves, botões e ícones SVG locais.
- Tela Meu dia com três indicadores e painéis de tarefas e rotinas lado a lado em janelas amplas.
- Estado sem tarefas com botão Criar tarefa e cartão do Google Agenda dentro do painel.
- Ícones nas rotinas e menus de três pontos para editar e excluir registros.
- Progresso semanal calculado pelos dias programados e conclusões reais, respeitando a data de criação. A barra diária e os círculos semanais são atualizados ao concluir/desmarcar uma rotina.
- Finanças, projetos, tarefas, calendário, modais e mensagens usam o novo estilo.
- Backup no rodapé; configurações dão acesso ao backup e às instruções do Google.

O status do Google mostra a conexão real. Um banco não conectado não exibe o estado Conectado da imagem de referência. Nenhuma conta foi conectada durante a validação.

O banco continua no mesmo caminho e não há nova migração de dados nesta revisão. Os limites, lançamentos e demais registros da versão 3.0 são reutilizados. A busca do cabeçalho filtra a aba atual; nas finanças, abre a lista de lançamentos. Ícones de rotinas são escolhidos pelo título, com um ícone de repetição como padrão.

## Usar

Extraia a pasta inteira do ZIP, execute `instalar_windows.bat` e depois `iniciar_windows.bat`. Se for atualizar uma instalação existente, feche a janela antiga primeiro. A nova janela começa em 1440 × 900 pixels e também se adapta a tamanhos menores. O código continua sendo entregue como fonte Python, sem `.exe` empacotado.

## Validação

42 testes de backend passaram, incluindo os dois novos testes do progresso semanal. Todos os arquivos JavaScript passaram na verificação de sintaxe. As seis abas foram verificadas em 360, 768, 1280 e 1672 pixels, sem rolagem horizontal ou erros JavaScript. As quatro seções financeiras foram conferidas em 360, 768 e 1672 pixels.

Também foram conferidos: abrir o formulário pela tarefa vazia, concluir/desmarcar rotina, abrir a edição pelos menus, buscar no cabeçalho, salvar uma edição financeira, usar o backup nas configurações e abrir o formulário financeiro em uma janela pequena. Os testes visuais usaram Chromium, o backend Python e um banco separado com dados fictícios. A janela nativa pywebview/WebView2 ainda não foi executada nesta validação.
