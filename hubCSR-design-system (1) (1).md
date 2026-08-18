# hubCSR — Design System

Linguagem visual, tokens, componentes e princípios da **hubCSR** — infraestrutura de observabilidade institucional (B2B SaaS, pt-BR). Conecta estratégia, pessoas e execução numa base contínua de evidência, histórico e contexto. **Não** é LMS, intranet ou ERP — integra com o stack legado e adiciona continuidade, rastreabilidade e comprovação confiável conforme a operação escala.

**Público:** empresas brasileiras de médio/grande porte e seus times de ESG/CSR/compliance/pessoas, além das OSCs da rede.

---

## 1. Princípios

- **Sóbrio e estrutural.** Muito espaço em branco, neutros slate, hierarquia clara. A informação é a protagonista; a interface recua. Pense "dashboard de observabilidade institucional", não "app de consumo".
- **Um único gesto de marca.** O gradiente aparece raramente e com intenção: uma palavra-chave de headline, um trilho fino, uma marca pequena, um glow. **Nunca** como fundo de página ou atrás de texto de corpo.
- **Palavra antes do ícone.** Word-led. Tipografia e layout estruturado carregam o significado; glifos são restritos e silenciosos. **Sem emoji.**
- **Calma institucional.** Movimento curto e confiante — sem bounce, sem spring. Feedback desaturado: institucional, não alarmante.

---

## 2. Cor

Os neutros **slate** carregam ~90% de cada tela. O gradiente é o único gesto expressivo. A interação é ancorada no **azure** (azure é funcional; o gradiente é decorativo). **Verde** carrega significado de sustentabilidade / positivo / sucesso.

### Gradiente da marca
Amostrado do wordmark — verde → teal → ciano → azul → índigo.

```css
--brand-gradient: linear-gradient(96deg,
  #2EA84D 0%, #10A39A 34%, #029CE0 60%, #1976BD 80%, #2F2E87 100%);
--brand-gradient-soft: linear-gradient(120deg, #10A39A 0%, #1976BD 100%); /* fills, CTAs */
```

**Use em:** uma palavra-chave de headline (texto clipado), trilho de acento fino (1–4px), marcas pequenas, fills de progresso, glow de herói.
**Nunca em:** fundo de página inteira, atrás de texto de corpo, como cor funcional de ação (isso é papel do azure).

### Rampas

```css
/* Azure — ação primária, links, foco (500 = primary) */
--azure-50:#ECF7FD; --azure-100:#D2ECFA; --azure-200:#A6D9F4; --azure-300:#6FBFEC;
--azure-400:#2FA3E3; --azure-500:#0E88CD; --azure-600:#0A6FA9; --azure-700:#0A5985;
--azure-800:#0C4A6E; --azure-900:#0D3E5B;

/* Green — sustentabilidade / impacto / sucesso (500 = brand green) */
--green-50:#ECF8EF; --green-100:#D2EFDA; --green-200:#A6E0B6; --green-300:#6FCB88;
--green-400:#43B563; --green-500:#2EA84D; --green-600:#1F8B3D; --green-700:#1A6F33;
--green-800:#185A2C; --green-900:#134A25;

/* Indigo — profundidade / institucional (600 = brand indigo) */
--indigo-50:#EDEDF6; --indigo-100:#D5D5EC; --indigo-200:#ACADD7; --indigo-300:#7E80BE;
--indigo-400:#5557A5; --indigo-500:#3A3C90; --indigo-600:#2F2E87; --indigo-700:#26266F;
--indigo-800:#1F1F5A; --indigo-900:#181845;

/* Slate — neutros, ~90% das telas (900 = tema escuro) */
--slate-0:#FFFFFF; --slate-50:#F8FAFC; --slate-100:#F1F5F9; --slate-200:#E2E8F0;
--slate-300:#CBD5E1; --slate-400:#94A3B8; --slate-500:#64748B; --slate-600:#475569;
--slate-700:#334155; --slate-800:#1E293B; --slate-900:#0F172A; --slate-950:#080F1F;
```

### Semânticos
Levemente desaturados — institucional, não alarmante. Cada um tem uma superfície tintada suave para badges/banners.

```css
--success:#1F8B3D; --success-surface:#ECF8EF;
--warning:#B7791F; --warning-surface:#FBF1DF;
--danger:#D1453B;  --danger-surface:#FBECEA;
--info:#0E88CD;    --info-surface:#ECF7FD;
```

### Aliases semânticos (prefira estes nos componentes)

```css
--text-strong:var(--slate-900); --text-body:var(--slate-700); --text-muted:var(--slate-500);
--text-subtle:var(--slate-400); --text-on-brand:#FFFFFF; --text-link:var(--azure-600);
--surface-page:var(--slate-50); --surface-card:#FFFFFF; --surface-sunken:var(--slate-100);
--surface-inverse:var(--slate-900); --surface-hover:var(--slate-100);
--border-subtle:var(--slate-200); --border-default:var(--slate-300); --border-strong:var(--slate-400);
--action-bg:var(--azure-500); --action-bg-hover:var(--azure-600); --action-bg-active:var(--azure-700);
--ring:0 0 0 3px rgba(14,136,205,0.32); /* foco */
```

---

## 3. Tipografia

- **Display / headings:** Sora — geométrica, levemente arredondada (ecoa o wordmark). Bold 700–800 no hero, tracking `-0.02em`, line-height ~1.1.
- **Corpo / UI:** Figtree — humanista, alta legibilidade, line-height generoso 1.5–1.65.
- **Mono:** JetBrains Mono — IDs, códigos de ciclo (`2025.2`), timestamps, unidades, tags de status. Sinaliza "evidência / registro".
- **Overlines/eyebrows:** 11–12px, MAIÚSCULAS, tracking `0.12em`, mutadas.

> ⚠️ Fontes substitutas (Sora / Figtree / JetBrains Mono via Google Fonts) até o envio das webfonts oficiais.

```css
--font-display:'Sora', system-ui, sans-serif;
--font-body:'Figtree', system-ui, sans-serif;
--font-mono:'JetBrains Mono', ui-monospace, monospace;

--weight-regular:400; --weight-medium:500; --weight-semibold:600; --weight-bold:700; --weight-extra:800;

/* Headlines fluidas */
--text-fluid-2xl:clamp(2.75rem,6vw,4.5rem);   /* hero */
--text-fluid-xl:clamp(2.25rem,4.5vw,3.25rem);
--text-fluid-lg:clamp(1.875rem,3.5vw,2.5rem);

/* UI / corpo */
--text-2xl:1.5rem;  /* 24 títulos de seção */  --text-xl:1.25rem;  /* 20 títulos de card */
--text-lg:1.125rem; /* 18 lead */              --text-md:1rem;     /* 16 corpo */
--text-sm:.875rem;  /* 14 secundário */        --text-xs:.75rem;   /* 12 labels */
--text-2xs:.6875rem;/* 11 overline */

--leading-tight:1.1; --leading-snug:1.25; --leading-normal:1.5; --leading-relaxed:1.65;
--tracking-tight:-0.02em; --tracking-overline:0.12em;
```

---

## 4. Espaço, raio, elevação, movimento

**Grid base de 4px.** Padding de seção generoso (`--section-y` ~56–112px). Largura máx. de conteúdo 1200px.

```css
/* Espaçamento (4px base) */
--space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-5:20px;
--space-6:24px; --space-8:32px; --space-10:40px; --space-12:48px; --space-16:64px;
--space-20:80px; --space-24:96px; --space-32:128px;
--container-max:1200px; --container-prose:68ch;

/* Raio — cantos suaves, ecoando o wordmark */
--radius-sm:6px; --radius-md:10px /* input/control */; --radius-lg:14px /* card */;
--radius-xl:20px /* painel */; --radius-2xl:28px /* hero */; --radius-pill:999px;

/* Elevação — sombras frias, baixo spread. Cards quase planos; elevam só no hover/overlay. */
--shadow-sm:0 1px 3px rgba(15,23,42,.08), 0 1px 2px rgba(15,23,42,.04); /* card */
--shadow-md:0 4px 12px rgba(15,23,42,.08), 0 2px 4px rgba(15,23,42,.04);
--shadow-lg:0 12px 28px rgba(15,23,42,.12), 0 4px 8px rgba(15,23,42,.05); /* hover */
--shadow-xl:0 24px 56px rgba(15,23,42,.16), 0 8px 16px rgba(15,23,42,.06); /* overlay */
--shadow-brand:0 8px 24px rgba(14,136,205,.28); /* glow do CTA primário/brand */

/* Movimento — curto e confiante. Sem bounce, sem spring. Respeita prefers-reduced-motion. */
--ease-standard:cubic-bezier(.2,0,0,1); --ease-out:cubic-bezier(.16,1,.3,1);
--dur-fast:120ms /* hover/press */; --dur-base:200ms; --dur-slow:320ms /* painéis */;
```

- **Separação padrão:** hairline `1px solid --border-subtle`, não sombra. Cards brancos sobre `slate-50`.
- **No escuro** (hero/sidebar `#0F172A`): bordas brancas de baixa opacidade `rgba(255,255,255,.08–.16)` e fills `rgba(255,255,255,.04–.08)`.
- **Blur:** reservado para chrome flutuante sobre escuro/imagem (nav sticky: `blur(14px)` sobre `rgba(15,23,42,.82)`).
- **Estados:** hover do primário escurece (500→600) + glow; secundário/ghost ganham wash `slate-100`; cards elevam 2px. Press = `translateY(1px)` (sem scale). Foco = ring azure 3px.

---

## 5. Iconografia

Sistema **word-led e glyph-light**. Estado é comunicado por **ponto colorido + rótulo**, não por ícone. **Sem emoji.** Glifos de UI atuais são símbolos Unicode restritos (`→ ✓ ⌕ ◴ ◫ ◎ ⬡ ▤ +`), dimensionados e coloridos como texto.

> ⚠️ Placeholders. Para produção, adotar um set de linha consistente — recomendação **Lucide** (traço 1,5–2px, juntas arredondadas), que combina com o wordmark e com Sora.

---

## 6. Componentes

Namespace global: `HubCSRDesignSystem_82fcaa`. Casing de UI = **sentence case** sempre.

| Componente | Props principais |
|---|---|
| **Button** | `variant`: primary (azure, padrão) · brand (gradiente — só CTA de herói) · secondary (outline) · ghost · subtle · danger. `size`: sm/md/lg. `iconLeft`/`iconRight`, `fullWidth`, `disabled`. |
| **Badge** | `variant`: neutral/brand/success/warning/danger/info/indigo. `dot` para ponto de status à esquerda. |
| **Card** | `padding`: none/sm/md/lg. `interactive` (lift no hover). `accent` (trilho de gradiente à esquerda). |
| **Stat** | `label`, `value`, `unit`, `trend` + `trendDir` (up/down/flat), `hint`. Fonte display, tracking apertado. Use dentro de um Card. |
| **Avatar** | `name` (iniciais + alt), `src`, `size` (px), `status` (online/away/offline). Fallback = iniciais sobre tint índigo. |
| **Logo** | `variant` (light em superfície escura), `height`, `basePath`. Clear space ≈ x-height do wordmark. |
| **Input** | `label`, `hint`, `error` (sobrepõe hint, vira vermelho), `iconLeft`, `disabled` + `value`/`onChange`/`type`/`placeholder`. Foco mostra ring azure. |
| **Select** | `options` (strings ou `{value,label}`), `label`, `hint`, `placeholder`, `value`, `onChange`, `disabled`. |
| **Switch** | `checked`, `onChange` (recebe próximo boolean), `label`, `disabled`. |
| **Tabs** | `items` (strings ou `{value,label,count}`), `value`, `onChange`. Barra de tabs com sublinhado. |

**Banners semânticos** (compostos a partir dos tokens, não um componente): superfície tintada suave + borda da mesma família + glifo + título/descrição. Ex.: `success-surface` #ECF8EF / borda #D2EFDA.

---

## 7. Frentes (módulos da plataforma)

Cada frente carrega **uma cor de acento e um ícone duotone próprio** — distintos entre si, mas dentro da paleta da marca. Ícone duotone = duas tonalidades do mesmo matiz (sólido + tint claro). Frentes em piloto recebem a etiqueta **DEMO** (pill na cor da frente, canto superior direito do card).

| Frente | Cor sólida | Tint claro | Ícone |
|---|---|---|---|
| Trilhas & academias | `#1F8B3D` | `#A6E0B6` | capelo (mortarboard) |
| Mentorias *(DEMO)* | `#0E88CD` | `#A6D9F4` | balões de conversa |
| Comunidades | `#3A3C90` | `#ACADD7` | nós conectados |
| Regulatório | `#B7791F` | `#F2E0BD` | escudo + check |
| Voluntariado *(DEMO)* | `#10A39A` | `#9BDED7` | chevrons ascendentes |
| Parcerias OSCs | `#1976BD` | `#A6D9F4` | anéis entrelaçados |

Card da frente: branco, `border 1px #E2E8F0`, `radius 16px`, padding 24px; ícone 40px no topo-esquerda, DEMO opcional no topo-direita; título (Sora 600, 16px, slate-900) + descrição de uma linha (13px, slate-500).

---

## 8. Tom de voz

Calma, institucional, sênior e precisa. Lê-se como infraestrutura para quem decide — sem hype, sem exclamação, sem emoji.

- **O léxico é a marca.** Reutilize: *continuidade, rastreabilidade, evidência, contexto, leitura, base contínua, fio temporal, comprovação, ciclo, frente, observável.*
- **Pessoa:** fala da "hubCSR" em terceira pessoa; trata o leitor como a organização ("sua operação", "o que a empresa já executa"). Eventuais "Conectamos…", "Criamos…" (1ª pessoa do plural = o time). Evite imperativos casuais com "você".
- **Casing:** sentence case em tudo. Única exceção é o wordmark — **hubCSR** (lowercase "hub", uppercase "CSR", sem espaço).
- **Posicionamento negativo explícito:** "Não é um LMS." "Não substitui intranet ou ERP."
- **Claims medidos e defensáveis** — capacidade de ler e decidir, nunca mágica. Números só quando reais (% de conformidade, contagem de OSCs/ciclos); sem métricas de vaidade.
- **CTAs quietos e concretos:** "Ver como funciona", "Falar com o time", "Agendar conversa orientada", "Conhecer solução", "Entrar".

**Frases para emular:**
> A hubCSR torna o alinhamento estratégico observável.
> Uma frente para começar. Uma base para crescer.
> Continuidade, contexto e evidência exigem mais estrutura.

---

## Ressalvas

- Fontes são substitutas até o envio das webfonts oficiais.
- Ícones de UI são placeholders Unicode — recomenda-se Lucide em produção.
- O UI kit do app é uma reconstrução a partir das features descritas; o kit de marketing segue de perto o site público (https://hubcsr.tech/).
