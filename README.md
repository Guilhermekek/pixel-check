# pixel-check

Ferramenta pra ajudar a desenhar pixel art: aponta problemas enquanto você desenha no Aseprite
(degraus irregulares, banding, contorno grosso, pillow shading, pixel tremendo na animação...),
explica como corrigir e sugere a cor. Baseada nos princípios do livro *Pixel Logic* (Michafrar) e da
série *Pixel Grimoire* (Pedro Medeiros). Tudo só **aponta e sugere**: assimetria, luz e estilo podem
ser propositais, quem decide é o artista.

## Instalação

1. Python 3.10+ e Pillow: `pip install -r requirements.txt`
2. Copie os arquivos de `aseprite/` pra pasta de scripts do Aseprite
   (File > Scripts > Open Scripts Folder) e rode File > Scripts > Rescan Scripts Folder.
3. No topo de cada `.lua`, ajuste `SCRIPT` pro caminho do seu `pixelclean.py`
   (e `DATA_DIR` no `Pixel Check.lua`, pasta onde ficam os exemplos de treino).
4. Teste: `python pixelclean.py --test` deve imprimir `ok`.

```
pixelclean.py          o motor (todas as checagens e correções)
aseprite/              scripts do Aseprite (chamam o pixelclean.py)
paletas/               paletas fixas do jogo (use em todo sprite novo)
sprites/               seus desenhos: originais/, etapas/, finais/   (fora do git)
debug/                 mapas e comparações; pode apagar quando quiser (fora do git)
dados/                 exemplos de treino que você salvou no Pixel Check (fora do git)
```

## Enquanto desenha (Aseprite)

**Pixel Check** (File > Scripts > Pixel Check): analisa o frame atual. Na primeira vez o Aseprite
pergunta se o script pode rodar comandos: permita.
- Prévia: tamanho real, ampliado, silhueta e desfocado.
- Marcas na camada `check` + janela com o problema, como corrigir e "aplicar a cor sugerida".
- **Aplicar marcados** / **Desfazer aplicacao** mexem no desenho (Ctrl+Z também desfaz).
- Esconda a camada `check` pra ver o desenho limpo; apague antes de exportar.

**Pixel Check Animacao**: compara os frames da tag atual (ou todos, sem tag): pixel tremendo
(muda num frame só e volta), cor piscando (só existe em poucos frames) e pé mudando de altura.
Use em animações no tempo (idle, andar); numa rotação de direções o "tremendo" se desliga sozinho.

**Limpar Traco**: desenhe a linha rápido, selecione em volta dela (pegando o traço inteiro) e rode.
Reta vira degraus iguais; curva vira degraus só crescendo/diminuindo; as pontas ficam onde você
desenhou. Funciona melhor com a linha numa camada própria. Traço fechado (círculo): limpe em duas metades.

**Espelhar Direcoes**: numa rotação de 8 frames, gera o rascunho de 8←2, 7←3, 6←4 (ou o contrário),
com o personagem no mesmo lugar. Frame de destino vazio: copia em cada camada. Já tem desenho: vai pra
camada `espelho (rascunho)` e o seu desenho não é tocado. Coisas assimétricas (rabo de cavalo, alça)
ficam do lado errado: ajuste à mão.

Atalhos: Edit > Keyboard Shortcuts, procure o nome do script.

## Exemplos de treino (dados/)

Base pra, no futuro, uma IA aprender o seu estilo. **Nada é salvo sem você clicar.**
1. O 1º Pixel Check de um frame guarda o "antes" (temporário, fora do projeto).
2. Corrija à vontade, rode o Pixel Check quantas vezes quiser: o "antes" continua sendo o do começo.
3. Ficou bom? **Salvar exemplo** cria `dados/<data>_<sprite>_f<frame>/` com `antes.png`, `depois.png`,
   `comparacao.png` (pra conferir), `relatorio.txt`, `sugestoes.txt` e `decisoes.txt` (o que você aplicou).
4. Era só teste? **Descartar exemplo** joga o "antes" fora (o desenho não muda). Salvou errado? Apague a pasta.

## Pelo terminal

```
python pixelclean.py sprite.gif mapa.png --check              diagnóstico do GIF inteiro
python pixelclean.py sprite.gif saida.gif --merge 20          junta cores quase iguais (todos os frames)
python pixelclean.py sprite.gif saida.gif --ramps paleta.png  paleta fixa por rampas (pele, cabelo...)
python pixelclean.py sprite.gif saida.gif --clean mapa.png    pixels soltos só no rosto, punhos e botas
python pixelclean.py sprite.gif mapa.png --sym                aponta diferenças de simetria
python pixelclean.py rascunho.png saida.png --size 32 --palette paleta.png --outline 1a1c2c
python pixelclean.py --test
```

## Aviso de versão nova no Discord

Quando uma release é publicada no GitHub, `.github/workflows/discord-release.yml` manda uma mensagem
pro canal do Discord. Precisa do segredo `DISCORD_WEBHOOK` no repositório (URL do webhook do canal).
