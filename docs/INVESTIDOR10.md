# Investidor10 no Holy Planner

Se você acompanha seus investimentos no [Investidor10](https://investidor10.com.br), pode abrir a sua carteira dentro do Holy Planner.

## Vincular a sua carteira

1. No Investidor10, deixe a sua carteira **pública** e copie o link dela. O formato é `https://investidor10.com.br/wallet/public/NÚMERO`.
2. No Holy Planner, abra **Finanças → Investimentos → Vincular minha carteira**.
3. Escolha **Usar Investidor10**, cole o link (ou só o número) e salve.

O link fica só no seu banco local. Instalações novas começam sem carteira vinculada, no controle local.

## Usar a carteira

1. Clique em **Abrir carteira no aplicativo**. A página oficial abre em uma janela própria do Holy Planner, com os valores e gráficos fornecidos pelo Investidor10.
2. Os atalhos abrem diretamente **Posições**, **Proventos**, **Patrimônio**, **Rentabilidade** e **Lançamentos**. Dentro da página, a navegação é a do Investidor10.
3. Clicar novamente reutiliza a janela de consulta e carrega a seção escolhida. Fechar essa janela mantém o planner aberto. Fechar o planner também encerra a janela de consulta.
4. Para editar a carteira ou usar sua sessão habitual, clique em **Abrir no navegador** e entre na sua conta do Investidor10. Se uma página não carregar na janela do aplicativo, tente pelo navegador.

É necessário acesso à internet. A janela usa o Microsoft Edge WebView2 no Windows. Os dados exibidos e a disponibilidade da carteira dependem do Investidor10; o Holy Planner não mantém uma cópia offline da carteira.

## Entradas, saídas e aportes

O controle de entradas e saídas continua igual. Em **Lançamentos**, registre pagamentos, recebimentos e movimentos que alteram seu saldo disponível.

Em **Investimentos → Movimentos de investimentos no saldo local**, você ainda pode registrar aportes, resgates e rendimentos recebidos. Esta seção começa recolhida quando o Investidor10 está ativo.

Exemplo: se saíram R$ 500 da sua conta para investir, registre um **Aporte** de R$ 500 no Holy Planner para reduzir o disponível e registre a operação no Investidor10 para atualizar a carteira. O patrimônio de mercado fica no Investidor10. A valorização de um ativo não vira uma entrada de caixa automaticamente.

O mês selecionado no Holy Planner filtra os lançamentos locais. A página do Investidor10 tem seus próprios filtros e exibe seus dados atuais.

## Configuração

**Configurar carteira** permite mudar o nome e o link público ou escolher **Usar controle local**. Todos os lançamentos, saldos e limites existentes são preservados. A preferência e o link ficam no banco local e entram nos backups.

A validação aceita apenas carteiras públicas HTTPS do domínio `investidor10.com.br`, com identificador numérico. Links de seções são normalizados para o link principal; parâmetros de rastreamento não são encaminhados.

## Alcance deste acesso

Esta versão usa a página oficial em uma janela do aplicativo. Não é uma sincronização de dados por API: não importa automaticamente ativos, preços, dividendos ou operações, não soma o patrimônio da plataforma ao caixa local e não envia seus lançamentos para o Investidor10.

Não foi encontrada documentação de uma API pública de carteiras para conectar o Holy Planner. Foi usada a alternativa de acesso à própria página autorizada por você. Não há extração automática da página nem uso de endpoints internos.

O Holy Planner não solicita nem grava sua senha do Investidor10. A janela remota é criada sem a API Python do planner; ela não recebe acesso aos seus lançamentos, tarefas, arquivos ou backups. O modo privado padrão do pywebview foi mantido.

Referências verificadas em 06/10/2026: [suporte oficial](https://investidor10.com.br/suporte/) e [API do pywebview](https://pywebview.flowrl.com/api/).

## Atualização e validação

Extraia o novo ZIP, execute `scripts\instalar_windows.bat` se ainda não instalou as dependências nesta pasta e abra `scripts\iniciar_windows.bat`. O banco continua em `%LOCALAPPDATA%\HolyPlanner\planner.db`. A versão 3.2 acrescenta somente uma tabela de configuração da carteira e mantém os registros existentes.

Os 52 testes de regressão passaram, incluindo validação de links, persistência e backup da preferência, atualização de banco existente, preservação dos saldos e abertura/reutilização/fechamento da janela com um adaptador simulado. A interface foi revisada no navegador usando banco separado com dados fictícios. As páginas públicas de resumo, posições e proventos foram abertas no Investidor10.

A janela nativa do pywebview não foi executada neste ambiente de validação; sua abertura foi testada com um adaptador simulado. Use a alternativa no navegador se houver uma incompatibilidade com o WebView2 instalado no computador.
