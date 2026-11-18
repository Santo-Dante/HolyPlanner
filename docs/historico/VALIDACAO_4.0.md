# Validação do Holy Planner 4.0

Realizada em 13/10/2026, com bancos temporários separados do banco pessoal.

- **62 testes Python aprovados**, incluindo a suíte anterior de finanças, Google Agenda e persistência, mais metas, notas, sessões, planejamento de tarefas, migração e API web. Após o ajuste final da identificação do modo web, os quatro testes HTTP foram executados novamente e aprovados.
- **JavaScript:** verificação de sintaxe de app, produtividade, finanças, ponte web e service worker. O teste `node test_focus.js` confirmou tempo decorrido, pausa, reenvio após falha de conexão, ausência de novo envio depois de salvar e exclusão das pausas do histórico de foco.
- **Interface no navegador:** conexão por código, nova tarefa com horário e estimativa, movimentação de tarefa no quadro, criação de meta e nota, navegação semanal e sessão real de foco de um minuto, registrada no histórico.
- **Responsividade:** dez telas verificadas em 390 px; painel, semana, tarefas, metas, foco e finanças também em 320 px; oito telas principais em 1440 px. Nenhuma delas apresentou conteúdo excedendo horizontalmente a área principal. Console sem erros nas verificações finais.
- **Executável:** PyInstaller 6.22.3, Windows x64. Diagnóstico do binário confirmou recursos locais, importação do webview, SQLite, gravação de tarefa e consulta de produtividade. A janela nativa abriu com título “Holy Planner 4.0” e processo respondendo. A inspeção automatizada do conteúdo dessa janela não foi concluída porque a autorização da ferramenta de controle do computador expirou; os fluxos completos da interface foram verificados no navegador.
- **Distribuição:** não contém `planner.db`, arquivos de credenciais ou dados de demonstração. Código e arquivos de interface do pacote foram conferidos com a versão final.

## Limites da validação

O layout móvel foi verificado com viewport de navegador, não em um aparelho Android ou iPhone físico. Não foi instalada uma PWA em celular: isso exige um endereço HTTPS com certificado confiável, conforme APP.md. Não houve publicação em lojas, implantação de hospedagem, alteração de firewall, conexão de conta Google real nem movimentação financeira externa.

A prévia usa `.test-data/preview.db`. Esse arquivo é independente de `%LOCALAPPDATA%\HolyPlanner\planner.db`.
