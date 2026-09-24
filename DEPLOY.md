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
   `CORS_ORIGINS` (deixe em branco por enquanto, ajustamos no passo 7),
   `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `VAPID_PUBLIC_KEY`.
4. Para a chave privada do VAPID: em **Environment → Secret Files**, adicione
   um arquivo com o conteúdo da chave privada (ex: `vapid_private.pem`). O
   Render mostra o caminho onde ele fica montado — cole esse caminho em
   `VAPID_PRIVATE_PEM_PATH`.
5. Clique em **Apply**. O primeiro deploy demora alguns minutos.
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

- **Login "Continuar com Google"**: usa um endpoint da Emergent
  (`EMERGENT_OAUTH_SESSION_ENDPOINT`) para trocar o login do Google por uma
  sessão. Fora da Emergent, esse botão provavelmente não vai funcionar até
  ser reescrito para usar OAuth do Google diretamente. **Login por
  e-mail/senha não é afetado** e continua funcionando normalmente.
- **Recurso de IA** (`backend/routes/ai.py`): dependia do pacote privado
  `emergentintegrations`, que só existe no índice pip interno da Emergent (não
  está no PyPI público — por isso foi removido do `requirements.txt` neste
  commit, senão o `pip install` quebra em qualquer outro host). O código já
  trata essa ausência sem quebrar: a rota de IA simplesmente responde "
  indisponível" até alguém reescrevê-la para chamar OpenAI ou Gemini
  diretamente (os pacotes `openai` e `google-generativeai` já estão no
  `requirements.txt`).

Tudo o resto (biblioteca de séries, calendário, progresso, avaliações,
notificações push, cobrança Pro via Stripe, exportações) usa apenas
infraestrutura padrão e deve funcionar normalmente nesta hospedagem.
