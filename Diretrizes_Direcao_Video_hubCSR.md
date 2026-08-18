# Diretrizes de Direção de Vídeo — hubCSR

Este documento traduz o Design System e o tom de voz da **hubCSR** para a produção audiovisual (motion design, demos de produto e anúncios). O objetivo é garantir que toda peça de vídeo transmita a mesma **calma institucional, estrutura e clareza** da plataforma, facilitando o alinhamento com a equipe de criação.

## 1. Princípios de Motion e Direção
- **Foco na Informação (Word-led):** O texto e a interface são os protagonistas. Evite excesso de grafismos que não tenham função clara. A informação guia o olhar.
- **Movimento Sóbrio e Confiante:** A animação deve ser curta e direta. **Regra de ouro:** Sem efeito *bounce* (quique) ou *spring* (mola). Use curvas de aceleração padrão da UI (`cubic-bezier(.2,0,0,1)` ou `cubic-bezier(.16,1,.3,1)`) com durações entre 120ms e 320ms.
- **Sem Alarde:** O feedback visual das interfaces simuladas no vídeo deve ser desaturado e institucional. Nunca use animações que transmitam ansiedade ou erro crítico alarmante.
- **Ritmo Editorial:** O tempo de leitura na tela deve ser rigorosamente respeitado. Transições de cena devem ser limpas (cortes secos, deslizes suaves ou fades muito rápidos).

## 2. Direção de Arte em Vídeo
- **Cores e Fundos:** 
  - Aproximadamente **90% da tela** deve ser dominada pelos tons neutros (**Slate**). Fundos de vídeo devem usar o `slate-50` para cenas de claridade/operação ou `slate-900` para fechar a cartela final com peso institucional.
  - **Gradiente da Marca:** Deve ser usado com extrema restrição. Aplique apenas no fio condutor da narrativa (ex: a linha gráfica que conecta os pontos da operação), no glow de um botão primário ou na cartela de encerramento. **Nunca** como fundo inteiro ou atrás de parágrafos.
  - **Azure & Green:** Use Azure para destacar interações e a UI funcionando (cliques, links, foco). Use Green apenas para comunicar sucesso, impacto ou a conclusão de um ciclo.
- **Tipografia em Tela:**
  - **Sora (Display):** Para os *supers* (textos grandes de impacto na tela, ex: "Não é falta de sistema. É fragmentação.").
  - **JetBrains Mono:** Para destacar dados brutos, contadores de evidências, IDs, ou timestamps de ciclos (sinaliza "registro e verdade").
  - **Sem Emoji:** A comunicação é B2B sênior. O estado é comunicado por ponto colorido e rótulo, nunca por emojis.

## 3. Estrutura Narrativa (O Padrão hubCSR)
Com base nas peças de comunicação e fluxos de uso da plataforma, os vídeos devem seguir a estrutura lógica de **Fricção/Problema → Solução Observável → Decisão/Ação**.

### A. O Cenário Fragmentado (A Fricção)
- **Visual:** Elementos isolados. Caixas de texto simulando mensagens repetitivas (ex: *"Oi! Rapidinho... o vale-refeição..."*), planilhas soltas, ícones de Drive e LMS espalhados pela tela.
- **Mensagem:** Exponha o atrito operacional. A fila no RH (*"Dois dias parado"*), o retrabalho (*"Trilha sem evidência vira retrabalho"*), ou a falta de visibilidade (*"Política sem histórico vira risco"*).
- **Tom:** Constatação fria e realista do problema. Sem dramatização exagerada, apenas demonstrando a ineficiência do cenário atual.

### B. A Observabilidade (A Intervenção hubCSR)
- **Visual:** A interface da hubCSR entra em cena de forma imponente e limpa. Fios (linhas vetoriais) conectam o caos anterior, organizando os dados em uma base unificada.
- **Mensagem:** *"A hubCSR apara tudo em uma base só."* / *"Conhecimento que circula e responde sozinho."*
- **Ação na Tela:** Mostre o produto resolvendo o problema de forma autônoma. A IA respondendo à dúvida do RH citando a política correta, a centralização de obrigações (ex: 24 treinamentos pendentes organizados), o dashboard mostrando a leitura clara da operação.

### C. O Fechamento Institucional
- **Visual:** Fundo escuro e profundo (`slate-900` ou `indigo-900`), wordmark da hubCSR centralizado (com o gradiente sutil amostrado no wordmark).
- **Copy:** Frases de posicionamento curtas, maduras e defensáveis:
  - *"A empresa executa. A hubCSR mantém o fio."*
  - *"Menos esforço para acompanhar e comprovar."*
  - *"Uma frente para começar. Uma base contínua para crescer."*
- **Call to Action (CTA):** Quieto e concreto. Ex: *"Conhecer solução →"* (apontando para hubcsr.tech).

## 4. Checklist para Validação de Peças
- [ ] O fundo de tela e os cards da UI seguem a paleta *Slate* (muito espaço em branco e respiro)?
- [ ] O movimento das animações é direto e confiante (ausência total de *bounce/spring*)?
- [ ] O texto em tela está em *sentence case* (exceção apenas para o wordmark "hubCSR")?
- [ ] A locução ou os letreiros tratam a hubCSR na 3ª pessoa e o espectador como organização (ex: *"sua operação"*)?
- [ ] Emojis e grafismos infantis/casuais foram totalmente removidos?
- [ ] As telas demonstradas utilizam o estilo de sombras planas e hierarquia estabelecida no Design System?
