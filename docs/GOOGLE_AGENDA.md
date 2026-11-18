# Conectar o Holy Planner ao Google Agenda

A integração está implementada no aplicativo, mas a conta só fica conectada depois que você cria as credenciais e autoriza o acesso pelo navegador. Nenhuma credencial está incluída neste pacote.

## 1. Atualize o aplicativo

Feche o Holy Planner, extraia a nova versão e execute `scripts\instalar_windows.bat` novamente. A atualização instala as dependências do Google e mantém o banco de dados existente.

## 2. Crie um projeto no Google Cloud

1. Abra [Google Cloud Console](https://console.cloud.google.com/).
2. Crie ou selecione um projeto, por exemplo **Holy Planner**.
3. Em **APIs e serviços → Biblioteca**, procure **Google Calendar API** e ative a API.

## 3. Configure o OAuth

1. Abra **Google Auth Platform → Branding** e configure o nome do aplicativo, e-mail de suporte e contato.
2. Em **Audience / Público**, use **External / Externo** para uma conta Gmail pessoal. Se o app estiver em teste, adicione o e-mail que você usará em **Test users / Usuários de teste**. A opção Interno se aplica a organizações Google Workspace compatíveis.
3. Em **Data Access / Acesso a dados**, adicione os escopos:

```text
https://www.googleapis.com/auth/calendar.events
https://www.googleapis.com/auth/calendar.calendarlist.readonly
```

O primeiro permite ler e alterar eventos; o segundo permite listar suas agendas. O código escreve apenas eventos vinculados a itens do Holy Planner na sua agenda principal. Eventos criados fora do aplicativo são consultados, sem edição pelo Holy Planner.

4. Em **Clients / Clientes**, crie um cliente OAuth do tipo **Desktop app / Aplicativo para computador**.
5. Baixe o JSON e renomeie para **credentials.json**.
6. Coloque esse arquivo ao lado de `app.py`, dentro de `holy_planner`.

Esse arquivo não deve ser enviado nesta conversa ou incluído em um repositório público. O login acontece diretamente com o Google no seu navegador.

Referência oficial: [Quickstart Python do Google Agenda](https://developers.google.com/workspace/calendar/api/quickstart/python). Se o Google bloquear a autorização, confira o usuário de teste, o tipo de cliente e as políticas da conta. O modo de teste pode exigir novas autorizações; a tela oferece Reconectar.

## 4. Autorize sua conta

1. Abra `scripts\iniciar_windows.bat`.
2. Clique em **Conectar Google**.
3. Escolha sua conta no navegador e autorize as permissões solicitadas.
4. Volte ao aplicativo. A primeira sincronização começa automaticamente.

O endereço da agenda principal aparece na área de conexão. Ela recebe os itens locais já cadastrados e os próximos que você criar. Para enviar para outra conta, use Reconectar e selecione a conta desejada. Os eventos na conta anterior são preservados.

## Como funciona

| Origem | Comportamento |
|---|---|
| Eventos existentes no Google | Aparecem no calendário e em Meu dia com a identificação Google Agenda. São lidas as agendas com acesso de leitura completo. |
| Evento alterado ou excluído no Google | A consulta do mês é atualizada na próxima sincronização bem-sucedida. |
| Tarefa com prazo | Enviada à agenda principal como evento de dia inteiro. |
| Projeto com prazo | Enviado como evento de dia inteiro e mostrado no calendário local. |
| Tarefa ou projeto sem prazo | Permanece local, pois não tem data para o calendário. |
| Rotina | Somente no aplicativo. Nunca é enviada ao Google. |
| Tarefa concluída | O título do evento recebe ✓. Reabrir retira esse prefixo. |
| Conclusão diária de rotina | Mantida no histórico local; não altera a série de eventos do Google. |
| Edição de tarefa/projeto local | Atualiza o evento vinculado, sem criar uma cópia adicional. |
| Exclusão de tarefa/projeto ou remoção do prazo | Remove seu evento vinculado; a interface informa isso na confirmação. |

As tarefas são **eventos do Google Agenda**, não itens do serviço Google Tasks. Esta versão não adiciona horário aos itens locais. Eventos vindos do Google preservam o horário e são exibidos no fuso da agenda principal, informado na área de conexão. Eventos com vários dias aparecem em cada dia abrangido.

**Edite na origem:** eventos criados no Google são consultados aqui e editados no Google. Itens criados no Holy Planner devem ser editados no Holy Planner. Alterações feitas diretamente no Google em um evento exportado não modificam a tarefa ou projeto local e podem ser substituídas pela próxima edição no aplicativo. Um evento exportado removido diretamente no Google poderá ser recriado após uma edição local.

## Atualização automática e funcionamento offline

- A sincronização ocorre ao abrir o app conectado, após salvar/excluir tarefas ou projetos, ao mudar o mês e a cada 60 segundos enquanto o aplicativo estiver aberto.
- **Sincronizar** permite atualizar imediatamente.
- A consulta busca o mês em exibição no calendário; nas outras áreas, o mês atual. Navegue até outros meses para carregá-los.
- As alterações locais aguardam a próxima sincronização se faltar internet. O aplicativo salva primeiro no SQLite.
- Meses já consultados ficam disponíveis em cache. A mensagem de erro informa quando não foi possível atualizar; o horário de última sincronização não avança em uma rodada com falhas.
- Se o aplicativo estiver fechado, não há sincronização até a próxima abertura.
- O identificador remoto é salvo antes do envio, permitindo repetir uma criação após falha de rede sem duplicar o evento.

## Credenciais e desconexão

O token de acesso é guardado pelo `keyring`, usando o gerenciador de credenciais do sistema (no Windows, Credential Manager). Ele não é salvo no banco de dados, no HTML ou no ZIP de backup. Em outros sistemas, um backend funcional do keyring é necessário.

**Desconectar** interrompe a sincronização, remove a credencial local e limpa o cache de eventos do Google. Os itens locais e os eventos já enviados ao Google permanecem. Para revogar também a autorização concedida ao aplicativo, use a área de conexões da sua Conta Google.

## Se não conectar

- `No module named ...`: execute `scripts\instalar_windows.bat` e depois `scripts\iniciar_windows.bat`.
- `credentials.json` ausente: confira o nome e se o arquivo está na mesma pasta de `app.py`.
- Cliente incorreto: baixe credenciais OAuth para **Aplicativo para computador**, não uma chave de API nem uma conta de serviço.
- Acesso bloqueado: confira API ativada, escopos, usuário de teste e restrições da organização.
- Autorização expirada: clique em Reconectar.
- Falha de rede ou limite temporário: os dados locais permanecem salvos; tente Sincronizar mais tarde.

## Validação desta entrega

Os testes usam uma API Google simulada para verificar criação, edição, exclusão, isolamento das rotinas, migração de vínculos, fuso horário, cache, recuperação de falhas e ausência de duplicação. A interface foi exercitada em Chromium com a ponte simulada. Não houve conexão a uma conta Google real nesta entrega; a validação final exige suas credenciais e autorização no computador.

## Rotinas que já estavam no Google antes da versão 2.5

A atualização interrompe a sincronização dessas rotinas e mantém os eventos remotos existentes. Editar ou excluir a rotina no aplicativo não modifica sua antiga série no Google. Para removê-la da agenda, exclua a série diretamente no Google Agenda. O aplicativo mantém os identificadores antigos apenas para não importar essas séries novamente como duplicatas. Vínculos antigos sem origem identificável são preservados pelo mesmo motivo.
