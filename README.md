# Orçamentos JM — App Android

Aplicativo Android (Python + KivyMD) para criação de **orçamentos** e **ordens de
serviço**, com geração de **PDF profissional**. É a versão mobile do sistema
desktop original da JM Serviços, com personalização de marca e backup na nuvem.

## Funcionalidades

- **Clientes**: cadastro, edição, exclusão e busca; reaproveitáveis nos orçamentos.
- **Orçamentos**: itens (descrição, quantidade, unidade, valor), desconto em R$ ou %,
  condições comerciais, ordem de serviço e até 4 fotos por orçamento.
- **PDF**: documento com cabeçalho e logomarca, dados do cliente, tabela de itens,
  totais/desconto, condições, assinatura, registro fotográfico e a ordem de serviço
  em página própria. Numeração automática `ORC-AAAA-NNN`.
- **Dashboard**: total de orçamentos, clientes, valor total e aprovados; recentes.
- **Personalização**: nome, CNPJ, endereço, telefone, e-mail, **logomarca**, tema
  claro/escuro e **cor principal**. Esses dados alimentam automaticamente o PDF.
- **Backup na nuvem**: gera um arquivo `.json` com todos os dados e abre a folha de
  compartilhamento do Android — escolha **Salvar no Drive** (Google Drive), e-mail
  ou WhatsApp. Restauração a partir de um arquivo de backup.

## Como gerar o APK pelo GitHub (recomendado)

Você não precisa instalar nada no computador. O projeto já inclui um fluxo do
**GitHub Actions** que compila o APK nos servidores do GitHub.

1. **Crie um repositório** no GitHub (pode ser privado).
2. **Envie estes arquivos** para o repositório. Pela web: “Add file → Upload files”,
   arraste tudo (incluindo a pasta `.github`) e confirme. Ou, pelo terminal:
   ```bash
   git init
   git add -A
   git commit -m "App Orçamentos JM"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
   git push -u origin main
   ```
3. **Aguarde a compilação.** Abra a aba **Actions** do repositório. O fluxo
   “Build Android APK” roda automaticamente (a primeira vez leva ~15–25 min).
4. **Baixe o APK.** Quando o item ficar verde, abra-o, role até **Artifacts** e
   baixe **apk** (um .zip com o arquivo `.apk` dentro).
5. *(Opcional)* Crie uma **Release** para ter um link permanente para baixar direto
   no celular.

## Instalar no celular

1. Transfira o `.apk` para o telefone (cabo, Google Drive, WhatsApp etc.).
2. Toque no arquivo. O Android pedirá para permitir **“instalar apps desconhecidos”**
   para o app que está abrindo o arquivo (Arquivos/Chrome) — autorize.
3. Toque em **Instalar**. Pronto.

O APK é um *build* de depuração, assinado com chave temporária — perfeito para uso
pessoal/sideload. Para publicar na Play Store é preciso um *build* de release
assinado com a sua própria chave.

## Estrutura do projeto

| Arquivo | Função |
|---|---|
| `main.py` | App e interface (KivyMD). |
| `database.py` | Banco SQLite: clientes, orçamentos, perfil da empresa e configurações. |
| `pdf_generator.py` | Geração do PDF (ReportLab). |
| `backup.py` | Exportar/restaurar backup e compartilhar para a nuvem. |
| `paths.py` | Diretórios de dados/arquivos no Android e no desktop. |
| `util.py` | Formatação de moeda no padrão brasileiro. |
| `buildozer.spec` | Configuração de build do APK. |
| `.github/workflows/android-build.yml` | Compilação automática no GitHub Actions. |
| `data/` | Ícone e tela de abertura. |

## Testar no computador (opcional)

O app roda no desktop para desenvolvimento:
```bash
pip install "kivy==2.3.0" "kivymd==1.1.1" pillow reportlab plyer
python main.py
```

## Ajustes úteis

- **Compatibilidade com celulares antigos**: em `buildozer.spec`, troque
  `android.archs = arm64-v8a` por `android.archs = arm64-v8a, armeabi-v7a`
  (o build fica mais lento, mas cobre aparelhos mais antigos).
- **Nome/identificador do app**: campos `title`, `package.name` e `package.domain`
  no `buildozer.spec`.
