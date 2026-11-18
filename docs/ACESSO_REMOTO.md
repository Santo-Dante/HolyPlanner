# Usar o Holy Planner fora de casa · 5.0

O servidor do celular (`iniciar_celular.bat`) funciona só na rede de casa. Para acessar de qualquer lugar **sem abrir portas no roteador e sem colocar seus dados na internet**, use o [Tailscale](https://tailscale.com): uma rede privada e criptografada entre os seus próprios aparelhos. O plano pessoal é gratuito.

> Nunca encaminhe a porta 8765 no roteador. Com o Tailscale, só os aparelhos da sua conta enxergam o computador.

## 1. Instalar

1. Instale o Tailscale no **computador** (Windows) e no **celular** (Android ou iPhone).
2. Entre com a **mesma conta** nos dois.
3. No computador, abra o Tailscale e anote o endereço da máquina: um IP que começa com `100.` ou um nome como `meu-pc.tailnet-1234.ts.net` (em **Admin console → Machines**).

## 2. Abrir o servidor

No computador, abra `iniciar_celular.bat` (pasta do executável) ou `scripts\iniciar_web.bat` (código-fonte), como em casa. A janela mostra o código de conexão.

No celular, com o Tailscale ligado, abra:

```text
http://100.x.y.z:8765
```

Digite o código de conexão. Pronto: funciona no 4G, no trabalho ou viajando, desde que o computador esteja ligado, com o Tailscale e a janela do servidor abertos.

O tráfego entre os aparelhos é criptografado pelo próprio Tailscale (WireGuard), mesmo usando `http://`.

Se não abrir, permita o Holy Planner (ou o Python) no Firewall do Windows também para a rede do Tailscale.

## 3. (Opcional) HTTPS para instalar como app no celular

Para instalar a PWA no Android/iPhone, o navegador exige HTTPS com certificado confiável. O Tailscale gera um gratuito:

1. No **Admin console → DNS**, ative **MagicDNS** e **HTTPS Certificates**.
2. No computador, em um terminal na pasta do Holy Planner:

   ```powershell
   tailscale cert meu-pc.tailnet-1234.ts.net
   ```

   Isso cria `meu-pc.tailnet-1234.ts.net.crt` e `.key` na pasta. A chave (`.key`) é privada: não a compartilhe nem a envie junto com o programa.

3. Inicie o servidor com o certificado:

   ```powershell
   .\.venv\Scripts\python.exe app.py --web --lan --cert meu-pc.tailnet-1234.ts.net.crt --key meu-pc.tailnet-1234.ts.net.key
   ```

   No executável: `& '.\Holy Planner.exe' --web --lan --cert ... --key ...`

4. No celular, abra `https://meu-pc.tailnet-1234.ts.net:8765`, conecte com o código e use **Instalar app** (Android) ou **Compartilhar → Adicionar à Tela de Início** (iPhone).

O certificado vale cerca de 90 dias; repita o passo 2 para renovar.

## Deixar sempre disponível

- Em **Lembretes → Abrir o Holy Planner ao ligar o computador**, a janela abre sozinha com o Windows.
- Para o celular, coloque um atalho de `iniciar_celular.bat` na pasta Inicializar do Windows (`Win + R` → `shell:startup`).
- Configure o Windows para não suspender enquanto estiver na tomada, se quiser acesso a qualquer hora.

## Limites

O computador precisa estar ligado. Reiniciar o servidor gera um novo código de conexão. Não há hospedagem na nuvem: os dados continuam só no seu computador.
