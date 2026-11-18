# Planejar investimentos · Holy Planner 4.2

Abra **Planejar investimentos** no menu (ou **Finanças → Investimentos → Planejar investimentos ↗**). A aba junta o que você já registrou com cenários fictícios para enxergar o futuro.

## 1. Seu histórico real

- **Capital aportado registrado**: calculado automaticamente a partir das Finanças (capital investido inicial + aportes − resgates efetivados), mês a mês.
- **Valor da carteira**: o Holy Planner não importa dados do Investidor10. Uma vez por mês, copie o patrimônio total mostrado lá (botão **Ver patrimônio no Investidor10 ↗**) e use **Registrar valor**. Registrar a mesma data atualiza o valor.
- **Resultado estimado** = último valor informado − capital aportado registrado naquele mês.
- **Aporte médio mensal** = média dos aportes líquidos dos 6 meses completos anteriores. É usado como sugestão em novos cenários.

## 2. Calculadora de meta

Em **Quanto preciso para chegar lá?** escolha o valor que você quer ter e:

- **Quanto investir por mês**: informe até quando quer ter o valor. A calculadora mostra o aporte mensal necessário, o total aportado, os rendimentos e compara com o seu aporte médio atual (quanto falta por mês e quando você chegaria no ritmo atual).
- **Em quanto tempo chego lá**: informe quanto pode investir por mês e veja em quantos anos e meses atinge o valor.

Marque **O valor desejado é em dinheiro de hoje** para corrigir a meta pela inflação (R$ 500 mil de hoje valem mais em reais daqui a 10 anos). **Usar a da carteira** preenche a rentabilidade estimada dos seus registros. **Salvar como cenário** leva o resultado para o gráfico. Os campos ficam lembrados neste dispositivo.

## Rentabilidade da carteira

Com dois ou mais valores registrados, com pelo menos 2 meses de distância, o app estima a rentabilidade anual dos últimos 12 meses descontando os aportes e resgates do período (método Dietz modificado). É uma aproximação para calibrar os cenários, não substitui a rentabilidade oficial do Investidor10.

## 3. Cenários fictícios

Clique em **Novo cenário** e informe:

| Campo | O que faz |
| --- | --- |
| Ponto de partida | Último valor da carteira, capital registrado nas finanças ou outro valor fictício |
| Aporte mensal | Entra no fim de cada mês |
| Reajuste do aporte | Aumenta o aporte a cada 12 meses (ex.: 5% ao ano) |
| Rentabilidade | Taxa anual composta, aplicada todo mês sobre o saldo. Use uma taxa líquida se quiser considerar IR e taxas |
| Inflação estimada | Usada para mostrar os "valores de hoje" |
| Prazo | De 1 a 60 anos |
| Meta (opcional) | Mostra quando o cenário atinge o valor |
| Eventos fictícios | Aportes extras ou retiradas em um mês (13º, bônus, carro, viagem). Marque "Repetir todo ano" para eventos anuais |

A prévia no rodapé do formulário recalcula enquanto você digita. **Duplicar e testar** cria uma cópia para mudar um valor e comparar. Quando o cenário tem meta e não a atinge, o cartão mostra o aporte mensal que seria necessário. Retiradas maiores que o saldo retiram apenas o disponível e geram um aviso. Eventos no mês atual ou no passado não entram na projeção.

## 4. Comparar

- O gráfico mostra o histórico (linhas contínuas) e os cenários (tracejadas) a partir de hoje. Passe o mouse ou toque para ver os valores de cada mês.
- Marque/desmarque cenários na legenda para comparar. **Valores de hoje** desconta a inflação de cada cenário.
- **Ano a ano** detalha aportes, retiradas, rendimentos e saldo de cada ano.

As projeções usam taxas constantes e servem para comparar possibilidades; não são previsão nem recomendação. Os cenários não alteram lançamentos, saldos ou o Investidor10. Tudo fica no mesmo banco local e entra em **Salvar backup**. Ao abrir esta versão pela primeira vez, uma cópia `antes-planejamento-...db` é criada em `HolyPlanner\backups`.

## Lançamentos que se repetem (Finanças)

Ao criar um lançamento, use **Repetir todo mês** (2 a 60 meses) para salário, aluguel, assinaturas ou parcelas. Cada mês recebe um lançamento no mesmo dia (ou no último dia, em meses mais curtos). Os de datas futuras ficam como **Previsto** e entram nas projeções de cada mês; efetive-os quando acontecerem. Cada repetição pode ser editada ou excluída separadamente.
