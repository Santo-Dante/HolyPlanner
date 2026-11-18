# Holy Planner 5.0 — começar a usar

## Aplicativo para Windows

Abra **`Holy Planner.exe`** — gere a versão 5.0 com `scripts\gerar_app_windows.bat`; ela fica em **`dist\v5.0\Holy Planner\Holy Planner.exe`**. Para levar a outro computador, copie a pasta inteira: a pasta `_internal` precisa ficar junto do executável. Essa distribuição já inclui Python e as bibliotecas; não é necessário instalar Python. O componente Microsoft Edge WebView2 precisa estar disponível no Windows. Feche a versão anterior antes de abrir a nova; seus dados continuam no mesmo banco.

Para usar o código-fonte, continue abrindo `scripts\iniciar_windows.bat`. Se ainda não houver ambiente Python, execute `scripts\instalar_windows.bat` primeiro.

## Usar no celular e no computador

1. Na pasta do executável, abra **`iniciar_celular.bat`**. No código-fonte, use **`scripts\iniciar_web.bat`**.
2. Uma janela mostra o endereço do computador e um código de conexão. O navegador do computador abre automaticamente.
3. Conecte o celular à **mesma rede Wi-Fi**. Abra no navegador do celular o endereço indicado na janela, por exemplo `http://192.168.1.20:8765`.
4. Digite o código no planner. Cada dispositivo precisa se conectar uma vez; reiniciar o servidor gera outro código e encerra as sessões anteriores.
5. Mantenha o computador ligado e a janela do servidor aberta. Para encerrar o acesso pela rede, feche essa janela ou pressione Ctrl+C nela.

Se o Windows perguntar sobre o firewall, permita o aplicativo apenas na sua rede privada. Se aparecerem vários endereços, escolha o IPv4 da conexão Wi-Fi ou Ethernet usada pelo celular; interfaces de VPN e máquinas virtuais também podem aparecer. Redes de convidados podem impedir a comunicação entre dispositivos. Não encaminhe a porta 8765 no roteador.

O modo local HTTP funciona no navegador. Ele deve ser usado em rede de confiança: o código limita acesso, mas HTTP não criptografa o tráfego. O aplicativo não foi publicado em uma loja e não contém APK ou aplicativo nativo para iOS.

## Instalar como PWA

- **Windows:** abra `http://localhost:8765` no Chrome ou Edge. Use a opção de instalar aplicativo do navegador ou o botão “Instalar app”, quando disponível.
- **Android:** em uma conexão HTTPS confiável, abra no Chrome e use “Instalar app”.
- **iPhone/iPad:** em uma conexão HTTPS confiável, abra no Safari, toque em Compartilhar e depois em “Adicionar à Tela de Início”.

Para instalação completa no celular, é necessário **HTTPS com certificado confiável no dispositivo**. HTTP com um endereço de rede local não atende a esse requisito. O servidor aceita seu certificado e chave:

```powershell
.venv\Scripts\python.exe app.py --web --lan --cert caminho\certificado.pem --key caminho\chave.pem
```

Ou na versão empacotada:

```powershell
& '.\Holy Planner.exe' --web --lan --cert caminho\certificado.pem --key caminho\chave.pem
```

O nome ou IP acessado precisa constar no certificado. Configuração de domínio, certificado confiável, hospedagem pública e acesso fora de casa não foram realizados. Não é necessário ativá-los para usar o navegador na rede local.

Referência técnica: [requisitos de instalação de PWAs](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable).

## O que há de novo

- **5.0:** captura rápida, lembretes, revisão semanal, diário, áreas conectadas, importação de extrato, fichas de treino. Veja [ROTINA.md](ROTINA.md). Para usar fora de casa, [ACESSO_REMOTO.md](ACESSO_REMOTO.md).
- **4.2:** Planejar investimentos e calculadora de meta. Veja [PLANEJAMENTO.md](PLANEJAMENTO.md).

- **Meus treinos (4.1):** diário de musculação e cardio, cargas e repetições por série, repetição de treinos anteriores, filtros de período e gráficos de evolução por exercício/modalidade. Veja [TREINOS.md](TREINOS.md).
- **Meu dia:** prioridades, rotinas, metas e tempo de foco em um painel.
- **Minha semana:** navegue pelas semanas, crie tarefas para um dia e veja horários e duração estimada. Tarefas sem data ficam em uma lista para planejamento.
- **Tarefas:** lista e quadro de três colunas; filtros de projeto, prioridade e status. Use “Mover para” para mudar o status com mouse, teclado ou toque.
- **Metas:** objetivo numérico, progresso, unidade, descrição e prazo.
- **Modo foco:** ciclos configuráveis de 1 a 180 minutos, pausas curtas/longas, tarefa vinculada, pausar/continuar, contador persistente, histórico e gráfico semanal.
- **Minhas notas:** texto livre e notas fixadas no topo.
- **Visual:** temas claro e escuro, navegação lateral no computador e menu no celular.
- **Atalhos:** `N` cria tarefa, `/` abre busca, `Alt+1` abre Meu dia, `Alt+2` abre foco. Não são ativados ao editar formulários.

Finanças, projetos, rotinas, calendário e integração Google Agenda continuam disponíveis. Conectar ou desconectar a conta Google exige a janela nativa do computador; eventos em cache e sincronização da agenda conectada são acessíveis pelo navegador. No executável, coloque seu `credentials.json` ao lado do `.exe` se quiser configurar a integração. Credenciais não são incluídas na distribuição.

## Dados, conexão e backup

O banco permanece em `%LOCALAPPDATA%\HolyPlanner\planner.db`. Todos os dispositivos conectados usam esse banco. Ao atualizar um banco 3.x, é criada uma cópia em `HolyPlanner\backups\antes-produtividade-...db`; ao atualizar da versão 4.0, a cópia fica em `HolyPlanner\backups\antes-treinos-...db`. A cópia é feita antes de acrescentar as tabelas e campos novos. Não há substituição dos registros existentes.

O botão **Salvar backup** guarda a cópia no computador; no navegador também baixa o arquivo para o dispositivo. A exportação financeira CSV também é baixada pelo navegador. Para restaurar, encerre as janelas do planner e do servidor, preserve uma cópia do banco atual e substitua `planner.db` pelo backup.

O aplicativo nativo funciona offline. No navegador/PWA, a interface pode abrir sem internet após ser instalada, mas a consulta e edição dos dados exigem conexão com o servidor. Dados financeiros e respostas da API não ficam no cache do navegador. O timer em andamento continua pela hora de término, inclusive após suspender a tela; uma sessão concluída aguarda a conexão para ser registrada sem duplicação. Não existe sincronização de timers entre aparelhos nem notificação garantida com o app fechado. O histórico é compartilhado depois de salvo.

## Gerar novamente o executável

Execute `scripts\gerar_app_windows.bat`. O processo baixa o PyInstaller e cria a pasta `dist\v5.0\Holy Planner`. Envie a pasta inteira, nunca só o `.exe`. Os arquivos de dados e credenciais pessoais não são empacotados.

## Validação

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
node --check frontend\app.js
node --check frontend\productivity.js
node --check frontend\bridge.js
node --check frontend\sw.js
node --check frontend\workouts.js
```

Os testes cobrem persistência, migração de banco antigo, finanças, integração Google com transporte simulado, idempotência das sessões de foco, validações, autenticação, origem de requisições, métodos permitidos e bloqueio de acesso a arquivos privados. A prévia em `tools\preview_server.py` usa dados de demonstração separados em `.test-data`, sem ler seu banco pessoal.
