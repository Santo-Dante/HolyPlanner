# Validação · Holy Planner 4.1

Data: 20/10/2026.

- **71 testes Python aprovados**, incluindo os recursos existentes e 9 novos testes de treinos/API web.
- Novos testes: persistência e backup; exclusão em cascata; prevenção de duplicação; controle de revisão; validação sem alteração de registros; peso corporal; cardio sem distância; agrupamento por nome; sessões distintas no mesmo dia; filtros de data; ritmo com distância parcial; rollback após falha de gravação; migração com backup; acesso autenticado pelo navegador.
- JavaScript: sintaxe de `app.js` e `workouts.js` validada; testes existentes do timer de foco aprovados.
- Interface no navegador com banco isolado `.test-data/preview.db`: criação com duas séries de cargas distintas e cardio; repetição; edição; persistência após recarregamento; comparação de maior carga e ritmo de corrida.
- Layout verificado a 320, 390 e 1440 pixels CSS, sem transbordamento horizontal do conteúdo principal; formulário a 320 e 390 pixels sem transbordamento. Temas claro e escuro inspecionados.
- Executável Windows construído com PyInstaller e diagnóstico `--self-test` aprovado: frontend, arquivos dos treinos, gravação de sessão e volume calculado de 120 kg × rep.

O pacote contém código e interface, sem bancos pessoais, dados de demonstração ou credenciais. A verificação responsiva usa o navegador do computador; não representa teste em aparelho Android/iPhone físico. O acesso móvel permanece pelo servidor na rede local, conforme APP.md.
