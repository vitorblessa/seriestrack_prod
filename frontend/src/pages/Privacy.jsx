import { Link } from "react-router-dom";

/**
 * Public privacy policy. Required by Google Play Store — must be reachable
 * without login and return HTTP 200 to a static, human-readable page.
 * Domain-neutral: hosted at /privacy.
 */
export default function Privacy() {
    return (
        <div className="min-h-screen bg-background text-foreground/90 py-14 px-6" data-testid="privacy-page">
            <div className="max-w-3xl mx-auto space-y-6 leading-relaxed">
                <div className="flex items-center justify-between mb-8">
                    <Link to="/" className="text-primary font-bold text-lg">SeriesTrack</Link>
                    <Link to="/" className="text-sm text-foreground/60 hover:text-foreground">← Início</Link>
                </div>
                <h1 className="font-display text-4xl font-bold">Política de Privacidade</h1>
                <p className="text-foreground/50 text-sm">Última atualização: 25 de novembro de 2026.</p>

                <h2 className="font-bold text-xl mt-8">1. Quem somos</h2>
                <p>SeriesTrack é um aplicativo que ajuda usuários a acompanhar episódios de séries entre serviços de streaming. Esta política descreve como tratamos os dados pessoais de quem usa o app, tanto na versão web quanto na versão Android.</p>

                <h2 className="font-bold text-xl mt-8">2. Dados que coletamos</h2>
                <ul className="list-disc pl-6 space-y-2">
                    <li><strong>Cadastro:</strong> nome, e-mail, senha (armazenada com hash bcrypt) e, quando o usuário opta por entrar com o Google, também nome, e-mail e foto de perfil.</li>
                    <li><strong>Biblioteca e progresso:</strong> as séries que você adiciona, o status (assistindo, finalizada, etc.) e quais episódios marcou como vistos.</li>
                    <li><strong>Avaliações:</strong> notas de 1 a 5 e comentários que você opta por publicar.</li>
                    <li><strong>Preferências:</strong> plataformas de streaming selecionadas, tema, fuso, idioma.</li>
                    <li><strong>Notificações:</strong> endpoint e chaves criptográficas do seu navegador (Web Push) ou o token do seu aparelho Android (Firebase Cloud Messaging), usados apenas para enviar as notificações que você habilitou.</li>
                    <li><strong>Google Agenda (opcional):</strong> se você conectar sua agenda, guardamos a autorização concedida por você para criar e atualizar nela os eventos de estreia de episódios. Você pode desconectar quando quiser.</li>
                    <li><strong>Assinatura Pro (Stripe):</strong> identificador de sessão de checkout, ID de assinatura, status e valor pago. Nunca armazenamos o número do cartão — isso fica com o Stripe.</li>
                    <li><strong>Dados técnicos:</strong> IP, agent do navegador/app e logs de erro, apenas para segurança e diagnóstico.</li>
                </ul>

                <h2 className="font-bold text-xl mt-8">3. Como usamos</h2>
                <p>Os dados são usados exclusivamente para (a) manter sua conta e sessão, (b) sincronizar sua biblioteca entre dispositivos, (c) enviar as notificações que você habilitou, (d) processar sua assinatura Pro (via Stripe), (e) enviar e-mails de verificação de conta e de redefinição de senha, (f) prevenir fraude e abuso.</p>

                <h2 className="font-bold text-xl mt-8">4. Compartilhamento com terceiros</h2>
                <ul className="list-disc pl-6 space-y-2">
                    <li><strong>Stripe (EUA):</strong> processa pagamentos da assinatura Pro. Recebe seu e-mail e valor cobrado. Política: <a className="text-primary" href="https://stripe.com/privacy" target="_blank" rel="noreferrer">stripe.com/privacy</a>.</li>
                    <li><strong>Google (via login opcional):</strong> se você optar por entrar com o Google, o Google nos envia seu e-mail, nome e foto. Política: <a className="text-primary" href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">policies.google.com/privacy</a>.</li>
                    <li><strong>TMDB:</strong> as informações sobre séries vêm do The Movie Database. Nenhum dado seu é enviado para eles.</li>
                    <li><strong>Render (hospedagem do servidor), MongoDB Atlas (banco de dados) e Vercel (hospedagem do site):</strong> armazenam e processam os dados da sua conta para que o serviço funcione. Cada provedor trata os dados sob seus próprios termos de proteção de dados.</li>
                    <li><strong>Resend:</strong> envia os e-mails de verificação e de redefinição de senha. Recebe seu e-mail e o conteúdo da mensagem.</li>
                    <li><strong>Google Firebase Cloud Messaging:</strong> entrega as notificações no app Android. Recebe o token do aparelho e o texto da notificação.</li>
                    <li><strong>Google Gemini (recomendações com IA, recurso Pro):</strong> ao pedir recomendações, enviamos os títulos e o status das séries da sua biblioteca e suas notas e comentários de avaliação. Não enviamos seu e-mail nem sua senha.</li>
                    <li><strong>Sentry (monitoramento de erros, quando habilitado):</strong> recebe relatórios técnicos de falhas, configurado para não enviar dados pessoais identificáveis.</li>
                    <li><strong>GitHub (cópias de segurança):</strong> guarda de forma privada as cópias diárias do banco de dados descritas na seção 6.</li>
                </ul>
                <p>Alguns desses provedores processam dados fora do Brasil (por exemplo, nos Estados Unidos). Essa transferência é necessária para prestar o serviço e segue a LGPD.</p>
                <p>Não vendemos, alugamos ou compartilhamos seus dados com anunciantes.</p>

                <h2 className="font-bold text-xl mt-8">5. Armazenamento local</h2>
                <p>O app guarda no seu navegador/aparelho: token de sessão JWT, preferências de UI (tema, filtros de streaming) e um cache leve da biblioteca e a fila de alterações feitas sem conexão, para funcionamento offline. Não guardamos senha nem dados de cartão localmente.</p>

                <h2 className="font-bold text-xl mt-8">6. Retenção</h2>
                <p>Mantemos os dados enquanto sua conta existir. Ao excluir a conta (ver seção 8), todos os dados pessoais são removidos em até 7 dias, exceto registros de pagamento — que a legislação brasileira exige reter por 5 anos, e são anonimizados imediatamente. Mantemos cópias de segurança diárias do banco de dados, guardadas de forma privada, que expiram automaticamente em até 90 dias; por isso, dados excluídos podem permanecer apenas nessas cópias até que expirem, sem qualquer outro uso.</p>

                <h2 className="font-bold text-xl mt-8">7. Seus direitos (LGPD / GDPR)</h2>
                <p>Você pode a qualquer momento: acessar e corrigir as informações do seu perfil, baixar uma cópia dos seus dados (Configurações → Seus dados: arquivo JSON com tudo o que guardamos sobre você, ou CSV só com a biblioteca), exportar sua biblioteca para o Trakt ou para o calendário (iCal), e excluir sua conta permanentemente (ver seção 8). Solicitações adicionais: <a className="text-primary" href="mailto:contato@seriestrack.app">contato@seriestrack.app</a>.</p>

                <h2 className="font-bold text-xl mt-8">8. Exclusão de conta</h2>
                <p>Para excluir sua conta e todos os dados associados, acesse <Link className="text-primary" to="/delete-account">/delete-account</Link> ou vá em <strong>Configurações → Excluir minha conta</strong> dentro do app. A exclusão é imediata e irreversível.</p>

                <h2 className="font-bold text-xl mt-8">9. Crianças</h2>
                <p>SeriesTrack não é direcionado a menores de 13 anos e não coleta conscientemente dados dessa faixa. Se tomarmos conhecimento, os dados são removidos.</p>

                <h2 className="font-bold text-xl mt-8">10. Contato</h2>
                <p>Dúvidas sobre esta política: <a className="text-primary" href="mailto:contato@seriestrack.app">contato@seriestrack.app</a>.</p>
            </div>
        </div>
    );
}
