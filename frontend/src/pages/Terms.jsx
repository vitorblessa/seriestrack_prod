import { Link } from "react-router-dom";

export default function Terms() {
    return (
        <div className="min-h-screen bg-[#0A0A0C] text-white/90 py-14 px-6" data-testid="terms-page">
            <div className="max-w-3xl mx-auto space-y-6 leading-relaxed">
                <div className="flex items-center justify-between mb-8">
                    <Link to="/" className="text-[#FF2A54] font-bold text-lg">SeriesTrack</Link>
                    <Link to="/" className="text-sm text-white/60 hover:text-white">← Início</Link>
                </div>
                <h1 className="font-display text-4xl font-bold">Termos de Uso</h1>
                <p className="text-white/50 text-sm">Última atualização: 22 de setembro de 2026.</p>

                <h2 className="font-bold text-xl mt-8">1. Aceitação</h2>
                <p>Ao criar uma conta ou usar o SeriesTrack, você concorda com estes Termos e com nossa <Link className="text-[#FF2A54]" to="/privacy">Política de Privacidade</Link>.</p>

                <h2 className="font-bold text-xl mt-8">2. Conta</h2>
                <p>Você é responsável por manter suas credenciais em segurança. Só pode criar uma conta se tiver 13 anos ou mais. Você garante que as informações fornecidas são verdadeiras.</p>

                <h2 className="font-bold text-xl mt-8">3. Uso permitido</h2>
                <p>SeriesTrack é para uso pessoal e não comercial. É proibido: (a) fazer scraping ou uso automatizado que sobrecarregue o serviço; (b) enviar conteúdo ilegal, difamatório ou que viole direitos de terceiros; (c) tentar burlar limites do plano gratuito.</p>

                <h2 className="font-bold text-xl mt-8">4. Conteúdo do usuário</h2>
                <p>Suas avaliações e listas são de sua autoria. Ao publicá-las como públicas, você concede ao SeriesTrack licença não-exclusiva para exibi-las dentro do serviço. Você mantém a titularidade.</p>

                <h2 className="font-bold text-xl mt-8">5. Dados de séries (TMDB)</h2>
                <p>Informações de séries, sinopses, imagens e datas vêm do <a className="text-[#FF2A54]" href="https://www.themoviedb.org/" target="_blank" rel="noreferrer">The Movie Database (TMDB)</a>. SeriesTrack não é endossado ou certificado pelo TMDB.</p>

                <h2 className="font-bold text-xl mt-8">6. Assinatura Pro</h2>
                <ul className="list-disc pl-6 space-y-2">
                    <li>A assinatura Pro é cobrada mensalmente (R$ 12,90) ou anualmente (R$ 99,00) via Stripe.</li>
                    <li>Renovação automática, cancelável a qualquer momento em Configurações → Assinatura.</li>
                    <li>O cancelamento encerra ao fim do ciclo atual — sem reembolso proporcional.</li>
                    <li>Reembolsos totais podem ser solicitados em até 7 dias após a primeira cobrança, conforme o Código de Defesa do Consumidor (Art. 49).</li>
                </ul>

                <h2 className="font-bold text-xl mt-8">7. Disponibilidade</h2>
                <p>Fazemos esforços razoáveis para manter o serviço no ar 24/7, mas não garantimos disponibilidade ininterrupta. Interrupções podem ocorrer para manutenção ou por falhas em provedores externos (Google, Stripe, TMDB).</p>

                <h2 className="font-bold text-xl mt-8">8. Encerramento</h2>
                <p>Podemos suspender ou encerrar contas que violem estes Termos. Você pode encerrar sua conta a qualquer momento em <Link className="text-[#FF2A54]" to="/delete-account">/delete-account</Link>.</p>

                <h2 className="font-bold text-xl mt-8">9. Propriedade intelectual</h2>
                <p>Todo o código, marca, layout e conteúdo produzido pela SeriesTrack pertence à SeriesTrack. Você não recebe licença para revenda ou reprodução.</p>

                <h2 className="font-bold text-xl mt-8">10. Limitação de responsabilidade</h2>
                <p>Na máxima extensão permitida por lei, SeriesTrack não se responsabiliza por danos indiretos, incidentais ou consequenciais decorrentes do uso ou da indisponibilidade do serviço.</p>

                <h2 className="font-bold text-xl mt-8">11. Alterações</h2>
                <p>Podemos atualizar estes Termos. Mudanças relevantes serão comunicadas por e-mail ou notificação in-app com 30 dias de antecedência.</p>

                <h2 className="font-bold text-xl mt-8">12. Lei aplicável</h2>
                <p>Estes Termos regem-se pela lei brasileira. Foro da Comarca do usuário para questões de consumo; demais, foro de São Paulo/SP.</p>

                <h2 className="font-bold text-xl mt-8">13. Contato</h2>
                <p><a className="text-[#FF2A54]" href="mailto:contato@seriestrack.app">contato@seriestrack.app</a></p>
            </div>
        </div>
    );
}
