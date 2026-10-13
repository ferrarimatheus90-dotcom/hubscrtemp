# Tag NFC Pet – "Aproxime o celular" (30 mm)

Modelo 3D para impressão da tag de coleira em formato de gota, com cavidade interna
para uma tag NFC redonda de 25 mm e pausa de impressão para inserir a tag.

## Arquivos

| Arquivo | Uso |
|---|---|
| `tag_nfc_pet_30mm.3mf` | Arquivo principal. Um objeto com duas partes: **Corpo (preto)** e **Relevo (branco)**. Inclui a pausa na camada. |
| `tag_nfc_pet_30mm_unico.stl` | Corpo + relevo unidos numa única malha (para fatiadores que não leem 3MF). |
| `gerar_tag_nfc.py` | Script que gera os arquivos (parâmetros no topo). |
| `preview.png` | Vista superior, corte e vista 3D. |

## Dimensões

| Medida | Valor |
|---|---|
| Diâmetro do disco | 30 mm |
| Tamanho total (com alça) | 30 × 36,5 mm |
| Espessura do corpo | 4,0 mm (4,6 mm com relevo) |
| Cavidade da tag | Ø 25,4 mm × 0,6 mm, de z = 2,0 a z = 2,6 mm (encaixe justo) |
| Furo da argola | triângulo arredondado, ~8 × 6 mm |
| Relevo (NFC, pata, texto) | 0,6 mm de altura; sem anel na borda (`COM_BORDA = False` no script) |

A cavidade é justa para tag NFC adesiva de 25 mm (~0,3 mm de espessura). Para tag tipo "moeda" (até 1 mm),
mude `R_CAVIDADE` para 13.0 e `CAV_Z1` para 3.0 no script.

## Pausa para inserir a tag

Com camadas de **0,2 mm**, a cavidade ocupa as camadas 11 a 13. A pausa está gravada no
3MF para acontecer **antes da camada 14 (z = 2,8 mm)**, que é a primeira camada que fecha
a cavidade. Na pausa, encaixe a tag NFC no rebaixo e retome a impressão.

- **Bambu Studio / OrcaSlicer:** abra o 3MF como projeto (não "importar só geometria").
  A pausa aparece na régua de camadas. Se não aparecer, clique com o botão direito na
  camada 14 (z = 2,8) da régua vertical e escolha *Adicionar pausa*.
- **PrusaSlicer / Cura / outros:** fatie o 3MF ou o STL e adicione a pausa manualmente na
  camada cuja altura é 2,8 mm (com outra altura de camada, use a primeira camada acima de 2,6 mm).

Dica: a camada 14 é impressa como ponte sobre a tag. PLA/PETG fazem essa ponte de 26 mm sem
problema; se preferir, aumente a *altura da cavidade* no script.

## Duas cores

O relevo é uma parte separada dentro do mesmo objeto. Em impressoras com troca de filamento
(AMS etc.) atribua o filamento branco à parte **Relevo (branco)** e o preto ao **Corpo (preto)**.
Em impressoras de uma cor, imprima tudo junto ou exclua a parte de relevo.

Observação: as letras têm ~2,3 mm de altura e traço de ~0,6 mm. Imprimem com bico de 0,4 mm,
mas para melhor definição use bico de 0,2 mm ou aumente `TAM_FONTE` no script.

## Regenerar

```bash
pip install trimesh shapely manifold3d mapbox_earcut matplotlib numpy scipy networkx
python3 gerar_tag_nfc.py
```
