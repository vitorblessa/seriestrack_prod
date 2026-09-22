import { Link } from "react-router-dom";

/**
 * Public privacy policy. Required by Google Play Store — must be reachable
 * without login and return HTTP 200 to a static, human-readable page.
 * Domain-neutral: hosted at /privacy.
 */
export default function Privacy() {
    return (
        <div className="min-h-screen bg-[#0A0A0C] text-white/90 py-14 px-6" data-testid="privacy-page">
            <div className="max-w-3xl mx-auto space-y-6 leading-relaxed">
                <div className="flex items-center justify-between mb-8">
                    <Link to="/" className="text-[#FF2A54] font-bold text-lg">SeriesTrack</Link>
                    <Link to="/" className="text-sm text-white/60 hover:text-white">← Início</Link>
                </div>
                <h1 className="font-display text-4xl font-bold">Política de Privacidade</h1>
                <p className="text-white/50 text-sm">Última atualização: 22 de setembro de 2026.</p>

                <h2 className="font-bold text-xl mt-8">1. Quem somos</h2>
                <p>SeriesTrack é um aplicativo que ajuda usuários a acompanhar episódios de séries entre serviços de streaming. Esta política descreve como tratamos os dados pessoais de quem usa o app, tanto na versão web quanto na versão Android.</p>

                <h2 className="font-bold text-xl mt-8">2. Dados que coletamos</h2>
                <ul className="list-disc pl-6 space-y-2">
                    <li><strong>Cadastro:</strong> nome, e-mail, senha (armazenada com hash bcrypt) e, quando o usuário opta por entrar com o Google, também nome, e-mail e foto de perfil.</li>
                    <li><strong>Biblioteca e progresso:</strong> as séries que você adiciona, o status (assistindo, finalizada, etc.) e quais episódios marcou como vistos.</li>
                    <li><strong>Avaliações:</strong> notas de 1 a 5 e comentários que você opta por publicar.</li>
                    <li><strong>Preferências:</strong> plataformas de streaming selecionadas, tema, fuso, idioma.</li>
                    <li><strong>Notificações:</strong> endpoint e chaves criptográficas do seu navegador/aparelho para envio de notificações push (VAPID Web Push).</li>
                    <li><strong>Assinatura Pro (Stripe):</strong> identificador de sessão de checkout, ID de assinatura, status e valor pago. Nunca armazenamos o número do cartão — isso fica com o Stripe.</li>
                    <li><strong>Dados técnicos:</strong> IP, agent do navegador/app e logs de erro, apenas para segurança e diagnóstico.</li>
                </ul>

                <h2 className="font-bold text-xl mt-8">3. Como usamos</h2>
                <p>Os dados são usados exclusivamente para (a) manter sua conta e sessão, (b) sincronizar sua biblioteca entre dispositivos, (c) enviar as notificações que você habilitou, (d) processar sua assinatura Pro (via Stripe), (e) prevenir fraude e abuso.</p>

                <h2 className="font-bold text-xl mt-8">4. Compartilhamento com terceiros</h2>
                <ul className="list-disc pl-6 space-y-2">
                    <li><strong>Stripe (EUA):</strong> processa pagamentos da assinatura Pro. Recebe seu e-mail e valor cobrado. Política: <a className="text-[#FF2A54]" href="https://stripe.com/privacy" target="_blank" rel="noreferrer">stripe.com/privacy</a>.</li>
                    <li><strong>Google (via login opcional):</strong> se você optar por entrar com o Google, o Google nos envia seu e-mail, nome e foto. Política: <a className="text-[#FF2A54]" href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">policies.google.com/privacy</a>.</li>
                    <li><strong>TMDB:</strong> as informações sobre séries vêm do The Movie Database. Nenhum dado seu é enviado para eles.</li>
                    <li><strong>Emergent (infraestrutura):</strong> hospeda backend e banco. Assinamos contrato de tratamento de dados.</li>
                </ul>
                <p>Não vendemos, alugamos ou compartilhamos seus dados com anunciantes.</p>

                <h2 className="font-bold text-xl mt-8">5. Armazenamento local</h2>
                <p>O app guarda no seu navegador/aparelho: token de sessão JWT, preferências de UI (tema, filtros de streaming) e um cache leve da biblioteca para funcionamento offline. Não guardamos senha nem dados de cartão localmente.</p>

                <h2 className="font-bold text-xl mt-8">6. Retenção</h2>
                <p>Mantemos os dados enquanto sua conta existir. Ao excluir a conta (ver seção 8), todos os dados pessoais são removidos em até 7 dias, exceto registros de pagamento — que a legislação brasileira exige reter por 5 anos, e são anonimizados imediatamente.</p>

                <h2 className="font-bold text-xl mt-8">7. Seus direitos (LGPD / GDPR)</h2>
                <p>Você pode a qualquer momento: acessar seus dados (endpoint <code>/api/auth/me</code>), corrigir informações do perfil, exportar sua biblioteca (Configurações → Trakt export/iCal), e excluir sua conta permanentemente (ver seção 8). Solicitações adicionais: <a className="text-[#FF2A54]" href="mailto:contato@seriestrack.app">contato@seriestrack.app</a>.</p>

                <h2 className="font-bold text-xl mt-8">8. Exclusão de conta</h2>
                <p>Para excluir sua conta e todos os dados associados, acesse <Link className="text-[#FF2A54]" to="/delete-account">/delete-account</Link> ou vá em <strong>Configurações → Excluir minha conta</strong> dentro do app. A exclusão é imediata e irreversível.</p>

                <h2 className="font-bold text-xl mt-8">9. Crianças</h2>
                <p>SeriesTrack não é direcionado a menores de 13 anos e não coleta conscientemente dados dessa faixa. Se tomarmos conhecimento, os dados são removidos.</p>

                <h2 className="font-bold text-xl mt-8">10. Contato</h2>
                <p>Dúvidas sobre esta política: <a className="text-[#FF2A54]" href="mailto:contato@seriestrack.app">contato@seriestrack.app</a>.</p>
            </div>
        </div>
    );
}
