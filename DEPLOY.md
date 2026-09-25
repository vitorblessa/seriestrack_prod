# Guia de Deploy — SeriesTrack

Este projeto tem duas partes que precisam ser hospedadas separadamente:

- **Backend** (FastAPI + MongoDB) → Render (free tier)
- **Frontend** (React) → Vercel (free tier)

Siga a ordem abaixo — o backend precisa existir primeiro, porque o frontend
precisa saber a URL dele.

---

## 1. Banco de dados — MongoDB Atlas (grátis)

1. Crie uma conta em https://www.mongodb.com/cloud/atlas/register
2. Crie um cluster gratuito (M0).
3. Em **Database Access**, crie um usuário com senha.
4. Em **Network Access**, adicione `0.0.0.0/0` (permite acesso de qualquer IP —
   necessário porque o Render usa IPs dinâmicos no free tier).
5. Em **Connect → Drivers**, copie a connection string. Vai parecer com:
   `mongodb+srv://usuario:senha@cluster.mongodb.net`
   Guarde isso — é o `MONGO_URL`.

## 2. Chave da TMDB (grátis)

1. Crie uma conta em https://www.themoviedb.org/
2. Vá em **Configurações → API** e peça uma chave de API (aprovação é quase
   instantânea).
3. Copie o **"API Read Access Token"** (token longo, formato JWT — não é a
   "API Key" curta). Isso é o `TMDB_READ_TOKEN`.

## 3. Chaves VAPID (notificações push — opcional, mas recomendado)

No seu computador, com Node instalado:
```
npx web-push generate-vapid-keys
```
Isso gera uma chave pública e uma privada. Guarde os dois valores.

## 4. Stripe (cobrança — pode ficar em modo teste por enquanto)

1. Crie uma conta em https://dashboard.stripe.com/register
2. Em **Developers → API keys**, copie a chave pública (`pk_test_...`) e a
   secreta (`sk_test_...`).
3. Rode `backend/setup_stripe.py` (localmente, com essas chaves nas variáveis
   de ambiente) para criar os produtos/preços do plano Pro no Stripe, se ainda
   não existirem.
4. O webhook secret (`STRIPE_WEBHOOK_SECRET`) só é necessário depois que o
   backend já estiver no ar — volte a este passo no final (item 8).

---

## 5. Deploy do backend — Render

1. Crie uma conta em https://render.com e conecte sua conta do GitHub.
2. Clique em **New → Blueprint**, selecione o repositório `seriestrack_prod`.
   O Render vai detectar o `render.yaml` na raiz automaticamente.
3. Preencha as variáveis marcadas como obrigatórias no painel (as que não têm
   um valor padrão): `MONGO_URL`, `TMDB_READ_TOKEN`, `ADMIN_PASSWORD`,
   `CORS_ORIGINS` (pode usar `*` por enquanto, ajustamos no passo 7),
   `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `VAPID_PUBLIC_KEY`.
4. Para a chave privada do VAPID: cole o valor da chave privada gerada por
   `npx web-push generate-vapid-keys` diretamente em `VAPID_PRIVATE_PEM_PATH`
   (apesar do nome sugerir um caminho de arquivo, o `pywebpush` usado neste
   projeto aceita a string da chave diretamente — não precisa subir arquivo
   nenhum). Não cole o conteúdo de um `.pem` completo aqui, só a string curta
   que o `web-push` gera.
5. Clique em **Apply**. O primeiro deploy demora alguns minutos.

   > A versão do Python é fixada em `3.12.3` via variável de ambiente
   > `PYTHON_VERSION` (já definida no `render.yaml`) e também em
   > `backend/.python-version`, como reforço. Sem isso, o build falha com um
   > conflito de dependências entre `google-api-core` e `grpcio-status`,
   > porque o Render usa Python 3.14 por padrão, mais novo do que as versões
   > pinadas no `requirements.txt` suportam.
6. Quando terminar, você terá uma URL tipo
   `https://seriestrack-backend.onrender.com`. Teste abrindo
   `https://seriestrack-backend.onrender.com/api/` (ou o endpoint de health
   que preferir) para confirmar que respondeu.

   > Nota: no free tier, o Render "dorme" o serviço após ~15 min sem uso, e a
   > próxima requisição demora ~30s pra acordar. Normal para testes; para
   > produção séria, considere o plano pago.

## 6. Deploy do frontend — Vercel

1. Crie uma conta em https://vercel.com e conecte o GitHub.
2. **Add New → Project**, selecione `seriestrack_prod`.
3. Em **Root Directory**, clique em "Edit" e selecione `frontend`.
4. Framework preset: Create React App (o Vercel deve detectar sozinho pelo
   `package.json`).
5. Em **Environment Variables**, adicione:
   `REACT_APP_BACKEND_URL` = a URL do Render do passo 5 (ex:
   `https://seriestrack-backend.onrender.com`)
   Adicione também `REACT_APP_GOOGLE_CLIENT_ID` com o Client ID do Google
   Cloud Console (veja "Login com Google" mais abaixo), se quiser esse
   login ativo.
6. Deploy. Você recebe uma URL tipo `https://seriestrack-prod.vercel.app`.

## 7. Conectar os dois (CORS)

Volte no Render, no serviço do backend, e edite a variável `CORS_ORIGINS`
para a URL exata do Vercel (sem barra no final):
```
CORS_ORIGINS=https://seriestrack-prod.vercel.app
```
Salve — o Render reinicia o serviço automaticamente.

## 8. Webhook do Stripe (depois que o backend estiver no ar)

1. No Stripe Dashboard → **Developers → Webhooks → Add endpoint**.
2. URL: `https://seriestrack-backend.onrender.com/api/billing/webhook` (ajuste
   o caminho conforme a rota real em `backend/routes/billing.py`).
3. Copie o **Signing secret** gerado e cole em `STRIPE_WEBHOOK_SECRET` no
   Render.

---

## Limitações conhecidas fora da plataforma Emergent

Este projeto foi originalmente construído e rodado dentro da plataforma
**Emergent**, que fornece dois atalhos proprietários que não existem em
hospedagem genérica:

## Login com Google

O login com Google não depende mais da Emergent — usa o fluxo oficial do
Google (Identity Services) direto:

1. Crie um OAuth Client ID em https://console.cloud.google.com → APIs &
   Services → Credentials → Create Credentials → OAuth client ID → Web
   application. Em "Authorized JavaScript origins", adicione a URL do seu
   frontend (ex: `https://seriestrack-prod.vercel.app`). Não precisa de
   "Redirect URIs".
2. O `GOOGLE_CLIENT_ID` do backend já vem preenchido no `render.yaml`.
3. No Vercel, adicione a variável `REACT_APP_GOOGLE_CLIENT_ID` com o mesmo
   Client ID (veja o passo 6 acima) e faça um redeploy do frontend.

Se o "Client ID" mudar no futuro, atualize nos dois lugares (Render e
Vercel).

## Sincronização automática com Google Calendar

Diferente do link .ics (que o Google atualiza sozinho, devagar), esta
sincronização usa a API do Google Calendar diretamente para criar/atualizar/
remover eventos assim que uma série é adicionada ou removida da biblioteca.
Precisa de configuração extra no mesmo OAuth Client do login:

1. **Ative a API**: console.cloud.google.com → APIs & Services → Library →
   procure "Google Calendar API" → Enable.
2. **Adicione o escopo**: APIs & Services → OAuth consent screen → Edit →
   Scopes → Add or Remove Scopes → marque
   `.../auth/calendar.events` → Save.
3. **Adicione o redirect URI**: APIs & Services → Credentials → abra o mesmo
   OAuth Client ID do login → em "Authorized redirect URIs", adicione
   `https://seriestrack-prod.vercel.app/calendar/google/callback`.
4. **Copie o Client Secret** (na mesma tela do Client ID) e cole em
   `GOOGLE_CLIENT_SECRET` no Render — diferente do Client ID, esse valor é
   sensível e só é usado no backend.
5. `GOOGLE_CALENDAR_REDIRECT_URI` já vem preenchido no `render.yaml` com a
   URL certa; se o domínio do frontend mudar, atualize os dois (aqui e no
   passo 3 do Google Cloud) juntos.

O botão fica em **Configurações → Google Calendar (sincronização
automática)**. Ele cria um calendário separado chamado "SeriesTrack" na
conta do usuário (não mexe no calendário principal), e tem um botão
"Sincronizar agora" para reenviar tudo manualmente quando quiser.

## Recomendações por IA (Google Gemini)

O recurso de IA usa o Gemini diretamente (chave gratuita, sem cartão):

1. Vá em https://aistudio.google.com/apikey e clique em "Create API key".
   Pode usar o mesmo projeto do Google Cloud do login (item anterior) ou
   criar um novo — não precisa estar ligado ao mesmo projeto.
2. Copie a chave gerada (começa com `AIza...`).
3. No Render, edite a variável `GEMINI_API_KEY` e cole a chave. Salve — o
   serviço reinicia sozinho.

Não precisa mexer no frontend nem no Vercel para isso — a chamada é só do
backend para a API do Gemini. O plano gratuito do Gemini tem um limite de
requisições por minuto/dia (suficiente para uso pessoal); se ultrapassar,
o endpoint de recomendações vai retornar erro até o limite resetar.

Tudo o resto (biblioteca de séries, calendário, progresso, avaliações,
notificações push, cobrança Pro via Stripe, exportações) usa apenas
infraestrutura padrão e deve funcionar normalmente nesta hospedagem.
