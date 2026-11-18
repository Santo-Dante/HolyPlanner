# Holy Planner 5.0 · o app trabalhando pela sua rotina

A versão 5.0 reduz o quanto você precisa lembrar e digitar. As novidades, em ordem de uso:

## Captura rápida (tecla Q)

Pressione **Q** em qualquer tela (ou o botão **Captura rápida** no topo) e escreva como falaria:

| Você escreve | Vira |
|---|---|
| `pagar luz 180 dia 15` | Saída **prevista** de R$ 180 no dia 15 |
| `gastei 45,90 no mercado` | Saída **efetivada** hoje, categoria Alimentação |
| `recebi salário 5000` | Entrada efetivada |
| `aporte 1000 no tesouro` | Aporte |
| `ligar para o dentista amanhã às 9h` | Tarefa amanhã às 09:00 |
| `reunião sexta 14:30 urgente` | Tarefa na sexta, prioridade Alta |
| `supino 4x10 60kg, agachamento 3x12 80kg` | Treino de hoje com as séries |
| `corrida 30min 5km` | Cardio de hoje |
| `nota: ideia para o fim de semana` | Nota |

Antes de salvar, o app mostra como entendeu e você pode trocar o tipo ou corrigir os campos. Datas aceitas: hoje, amanhã, ontem, dia 15, 20/12, dias da semana. Se o "dia 5" já passou, vai para o mês seguinte.

> O atalho funciona com o Holy Planner aberto (janela ou navegador). Não é um atalho global do Windows.

## Lembretes e notificações

O sino no topo mostra o que precisa de atenção:

- tarefas de hoje e atrasadas;
- rotinas ainda abertas e o diário do dia, a partir do horário que você escolher (padrão 20h);
- contas previstas que vencem hoje ou amanhã, e previstos vencidos;
- valor da carteira do mês (a partir do dia 25, se você usa o planejamento);
- revisão semanal (domingo e segunda).

**Notificações:** na janela do Windows, aparecem como notificação do sistema; no navegador/celular, depois de tocar em **Permitir notificações neste navegador**. Cada lembrete avisa uma vez por dia.

**Abrir ao ligar o computador:** no sino, marque a opção para o Holy Planner abrir com o Windows. Assim os lembretes do dia funcionam mesmo se você esquecer de abrir o app.

> As notificações dependem do app aberto (pode ficar minimizado). Com ele totalmente fechado, nada é avisado.

## Revisão semanal

Menu **Revisão semanal**. No domingo (ou na segunda), em uns 10 minutos:

1. **Como foi:** tarefas concluídas e atrasadas, % das rotinas, foco, treinos, entradas/saídas, humor, energia e sono médios.
2. **Reflexão:** o que deu certo e o que mudar.
3. **Próxima semana:** três prioridades e um dia para cada tarefa atrasada ou sem data. Também mostra o que já está marcado e as contas previstas.

**Salvar revisão e plano** grava a reflexão e distribui as tarefas nos dias escolhidos. Use as setas para ver semanas anteriores.

## Áreas conectadas

- **Metas automáticas:** ao criar uma meta, escolha como acompanhar: treinos registrados, minutos de foco, conclusões de uma rotina (na semana, no mês ou desde o início) ou valor da carteira. O progresso se atualiza sozinho.
- **Rotina marcada pelo treino:** na rotina, marque *Marcar automaticamente quando eu registrar um treino*. Ao salvar um treino, ela é concluída naquele dia.
- **Tarefa que é conta:** ao criar uma tarefa com prazo, abra *É uma conta a pagar?* e informe o valor. Uma saída prevista é criada nas Finanças na mesma data.

## Finanças com menos digitação

- **Importar extrato:** em Finanças, **⇩ Importar extrato**. Aceita OFX (padrão dos bancos) e CSV com cabeçalho (Data, Descrição, Valor). Para fatura de cartão, marque *valores positivos são gastos*. O app sugere a categoria pelo que você já registrou e por palavras (mercado, uber, farmácia, Netflix…), marca possíveis duplicados e nunca importa o mesmo lançamento duas vezes.
- **Séries:** ao editar um lançamento criado com *Repetir todo mês*, escolha *Este e os próximos da série*. Para excluir, use **Excluir este e os próximos**.
- **Copiar limites:** em Limites do mês, **Copiar do mês anterior**.
- **Para gastar por dia:** na Visão geral e no Meu dia, o saldo depois de todos os previstos do mês dividido pelos dias que faltam.

## Treinos

- **Fichas:** em qualquer treino do histórico, **Salvar como ficha** (Treino A, B, C…). Depois, **Começar** abre o treino já com os exercícios e as cargas e repetições da última vez.
- **Sugestão de carga:** em cada exercício aparece a última vez e um botão *Tentar X kg* (+2,5 kg a partir de 20 kg; +1 kg abaixo). Use só se completou as repetições com boa técnica.
- **Descanso:** no formulário do treino, botões de 60 s, 90 s, 2 e 3 min, com som e vibração no fim.

## Diário

Menu **Diário** ou o cartão *Como você está hoje?* no Meu dia: humor e energia de 1 a 5, horas de sono e uma linha sobre o dia. Leva segundos. Com alguns dias registrados (pelo menos 3 em cada situação), o diário compara: humor com e sem treino, energia e foco depois de dormir 7 h ou mais, humor com as rotinas completas. São comparações dos seus registros, não conclusões médicas.

## Fora de casa

Veja [ACESSO_REMOTO.md](ACESSO_REMOTO.md): usar pelo celular em qualquer lugar com o Tailscale, sem abrir portas no roteador, e com HTTPS para instalar como app.

## Dados

Tudo continua no mesmo banco local e entra em **Salvar backup**. Ao abrir a 5.0 pela primeira vez, uma cópia `antes-5.0-…db` é criada em `HolyPlanner\backups`.
