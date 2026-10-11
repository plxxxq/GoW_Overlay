# GoW Overlay

[English](#english) | [Português](#português)

## English

GoW Overlay is a Windows utility that combines a Twitch chat overlay with automatic OBS display-capture control. It was originally created for crash-free *God of War* speedruns, particularly on systems where the OBS Game Capture hook may cause instability, and was later expanded for single-monitor and smaller-screen setups.

### Features

- Displays Twitch chat over the game without using the OBS Game Capture hook.
- Supports Twitch emotes, including animated emotes, plus optional BTTV, FFZ and 7TV emotes.
- Shows channel-point redemptions, subscription activity, incoming raids and Cheers/Bits alerts.
- Automatically enables or disables an OBS display-capture source according to the active window.
- Can operate as chat only, OBS control only or both.
- Supports multiple monitors and proportionally scales the overlay from a 1920×1080 reference layout.
- Includes configurable font, opacity, spacing, dimensions, position and message behavior.
- Keeps the Settings and Live Control windows out of OBS capture when supported by Windows.
- Optional phone remote control: scan a QR code (same Wi-Fi) to clear messages and toggle options from a web page.
- Shows an optional, nearly transparent shortcut hint in the corner of the screen (excluded from OBS capture) that can be turned off in Settings.
- Reconnects to Twitch automatically if the connection drops.
- Saves an optional event log for troubleshooting (one file per run, 10 most recent kept).
- Provides a system-tray icon with quick access to Live Control, Settings and Exit.

### Requirements

- Windows 10 or Windows 11
- OBS Studio with WebSocket enabled on port `4455` and no password
- A Twitch account for chat, redemption, subscription and Bits authorization
- Python 3 when building from source

### OBS configuration

1. Add a **Display Capture** source to the desired OBS scene.
2. Name the source `DP`.
3. Enable the OBS WebSocket server on port `4455` without a password.
4. Use **Application Audio Capture** separately if game audio is required.

Automatic OBS control can be disabled in the application settings. The Twitch chat overlay can also be disabled independently.

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `F9` | Remove chat messages |
| `F10` | Open Settings |
| `F11` | Show or hide Live Control |

### Phone remote control

Click **Remote** in Live Control and then **Enable** to show a QR code. Scan it with your phone (same Wi-Fi network as the PC) to open a web page with buttons to clear messages and toggle "Always show messages" and automatic DP/OBS control, plus connection status.

- It is off by default and only runs while enabled.
- The link contains a random secret token that changes every time it is enabled; requests without it are refused.
- It uses plain HTTP on the local network. Avoid public or shared networks.
- Windows Firewall may ask for permission the first time; allow private networks.
- Chat content and Twitch tokens are never sent to the phone.

### Logs

When enabled in Settings, the app writes an event log to `%LOCALAPPDATA%\GoW Overlay\Logs\`, one file per run (`overlay_YYYY-MM-DD_HH-MM-SS.log`), keeping the 10 most recent. The log includes chat messages and events, and stays only on your computer.

### Building from source

Clone or download the repository, open PowerShell in the project directory and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\build.ps1"
```

The script installs the required Python packages and creates:

```text
Desktop\GoW Overlay\GoW Overlay.exe
```

### Privacy

Twitch authorization uses Twitch's official device authorization flow. The application never receives or stores the user's Twitch password. Access and refresh tokens, along with local settings, are stored only in:

```text
%LOCALAPPDATA%\GoW Overlay
```

An optional event log is saved to `%LOCALAPPDATA%\GoW Overlay\Logs\`, one file per run (`overlay_YYYY-MM-DD_HH-MM-SS.log`), keeping the 10 most recent. It can be turned off in Settings (*Save log to file*).

`tokens.txt` and `config.json` are excluded from the repository through `.gitignore`.

The application communicates with Twitch services only after the user authorizes the requested features. The `bits:read` permission is used only to display Cheers/Bits alerts. Incoming raid notifications do not require an additional Twitch permission. When third-party emotes are enabled, the application requests public emote data and images from BTTV, FrankerFaceZ and 7TV; Twitch tokens and local settings are not sent to those providers. OBS communication is restricted to the local WebSocket server configured by the user. See the [Twitch Privacy Notice](https://www.twitch.tv/p/en/legal/privacy-notice/).

### Uninstallation

GoW Overlay is portable and does not include an installer. Delete `GoW Overlay.exe`, then optionally remove the following folder to erase locally stored settings and Twitch tokens:

```text
%LOCALAPPDATA%\GoW Overlay
```

### Project structure

```text
assets/              Application icon and splash image
src/gow_overlay.py   Main application source
build.ps1            Windows build script
version_info.txt     Windows executable metadata
```

---

## Português

O GoW Overlay é um utilitário para Windows que combina um overlay do chat da Twitch com o controle automático da captura de tela do OBS. Ele foi criado originalmente para evitar crashes durante speedruns de *God of War*, principalmente em sistemas nos quais o hook da Captura de Jogo do OBS pode causar instabilidade, e depois foi ampliado para quem utiliza apenas um monitor ou telas menores.

### Recursos

- Exibe o chat da Twitch sobre o jogo sem utilizar o hook da Captura de Jogo do OBS.
- Suporta emotes da Twitch, incluindo emotes animados, além de emotes opcionais do BTTV, FFZ e 7TV.
- Exibe resgates de pontos do canal, atividades de inscrições, raids recebidas e alertas de Cheers/Bits.
- Ativa ou desativa automaticamente uma fonte de captura de tela do OBS conforme a janela em foco.
- Pode funcionar somente com o chat, somente com o controle do OBS ou com os dois recursos juntos.
- Suporta vários monitores e redimensiona proporcionalmente o overlay a partir de um layout-base de 1920×1080.
- Permite configurar fonte, opacidade, espaçamento, dimensões, posição e comportamento das mensagens.
- Mantém as janelas de Configurações e Live Control fora da captura do OBS quando o Windows oferece suporte.
- Controle remoto opcional pelo celular: escaneie um QR code (mesma rede Wi-Fi) para limpar mensagens e alternar opções por uma página web.
- Exibe uma dica de atalhos opcional, quase transparente, no canto da tela (fora da captura do OBS), que pode ser desligada nas Configurações.
- Reconecta automaticamente à Twitch se a conexão cair.
- Salva um log de eventos opcional para diagnóstico (um arquivo por uso, mantendo os 10 mais recentes).
- Oferece um ícone na bandeja do sistema, com acesso rápido ao Live Control, às Configurações e à opção Sair.

### Requisitos

- Windows 10 ou Windows 11
- OBS Studio com o WebSocket ativado na porta `4455` e sem senha
- Uma conta da Twitch para autorizar a leitura do chat, resgates, inscrições e Bits
- Python 3 para compilar pelo código-fonte

### Configuração do OBS

1. Adicione uma fonte **Captura de tela** à cena desejada do OBS.
2. Dê à fonte o nome `DP`.
3. Ative o servidor WebSocket do OBS na porta `4455`, sem senha.
4. Utilize **Captura de Áudio do Aplicativo** separadamente caso precise do som do jogo.

O controle automático do OBS pode ser desativado nas Configurações. A exibição do chat da Twitch também pode ser desligada de forma independente.

### Atalhos do teclado

| Atalho | Ação |
| --- | --- |
| `F9` | Remove mensagens do chat |
| `F10` | Abre as Configurações |
| `F11` | Mostra ou oculta o Live Control |

### Controle remoto pelo celular

Clique em **Remoto** no Live Control e depois em **Ativar** para exibir um QR code. Escaneie com o celular (na mesma rede Wi-Fi do PC) para abrir uma página com botões para limpar mensagens e alternar "Sempre mostrar mensagens" e o controle automático do DP/OBS, além do status das conexões.

- Vem desligado por padrão e só funciona enquanto estiver ativado.
- O link contém um código secreto aleatório que muda a cada ativação; pedidos sem ele são recusados.
- Usa HTTP simples na rede local. Evite redes públicas ou compartilhadas.
- O Firewall do Windows pode pedir permissão na primeira vez; permita redes privadas.
- O conteúdo do chat e os tokens da Twitch nunca são enviados ao celular.

### Logs

Quando ativado nas Configurações, o aplicativo grava um log de eventos em `%LOCALAPPDATA%\GoW Overlay\Logs\`, um arquivo por uso (`overlay_AAAA-MM-DD_HH-MM-SS.log`), mantendo os 10 mais recentes. O log inclui mensagens do chat e eventos e fica somente no seu computador.

### Compilação pelo código-fonte

Clone ou baixe o repositório, abra o PowerShell na pasta do projeto e execute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\build.ps1"
```

O script instala os pacotes necessários do Python e cria:

```text
Área de Trabalho\GoW Overlay\GoW Overlay.exe
```

### Privacidade

A autorização utiliza o fluxo oficial de dispositivos da Twitch. O aplicativo nunca recebe nem armazena a senha da Twitch. Os tokens de acesso e renovação, junto às configurações locais, ficam armazenados somente em:

```text
%LOCALAPPDATA%\GoW Overlay
```

Um log opcional de eventos é salvo em `%LOCALAPPDATA%\GoW Overlay\Logs\`, um arquivo por uso (`overlay_AAAA-MM-DD_HH-MM-SS.log`), mantendo os 10 mais recentes. Ele pode ser desligado nas Configurações (*Salvar log em arquivo*).

Os arquivos `tokens.txt` e `config.json` são excluídos do repositório pelo `.gitignore`.

O aplicativo se comunica com os serviços da Twitch somente depois que o usuário autoriza os recursos solicitados. A permissão `bits:read` é usada apenas para exibir alertas de Cheers/Bits. Os avisos de raids recebidas não exigem uma permissão adicional da Twitch. Quando os emotes de terceiros estão ativados, o aplicativo solicita dados públicos e imagens de emotes ao BTTV, FrankerFaceZ e 7TV; os tokens da Twitch e as configurações locais não são enviados a esses provedores. A comunicação com o OBS fica restrita ao servidor WebSocket local configurado pelo usuário. Consulte o [Aviso de Privacidade da Twitch](https://www.twitch.tv/p/en/legal/privacy-notice/).

### Desinstalação

O GoW Overlay é portátil e não utiliza instalador. Exclua o arquivo `GoW Overlay.exe` e, opcionalmente, remova a pasta abaixo para apagar as configurações locais e os tokens da Twitch:

```text
%LOCALAPPDATA%\GoW Overlay
```

### Estrutura do projeto

```text
assets/              Ícone e imagem de carregamento
src/gow_overlay.py   Código principal do aplicativo
build.ps1            Script de compilação para Windows
version_info.txt     Metadados do executável no Windows
```

## License / Licença

This project is licensed under the MIT License.

Este projeto é distribuído sob a licença MIT.

## Code signing status / Assinatura de código

**English:** The SignPath Foundation application for free code signing was not approved, so release artifacts are unsigned. Because of this, Windows SmartScreen may show a "Windows protected your PC" warning when you first run `GoW Overlay.exe`; this is expected for unsigned apps and does not by itself mean the file is unsafe. The full source code is in this repository, and the executable is built from it with the included `build.ps1` and the GitHub Actions workflow, so you can review the code and build it yourself. Only download releases from this repository.

**Português:** A solicitação de assinatura de código gratuita da SignPath Foundation não foi aprovada, portanto os arquivos publicados não são assinados. Por isso, o Windows SmartScreen pode exibir o aviso "O Windows protegeu seu computador" ao abrir o `GoW Overlay.exe` pela primeira vez; isso é esperado em aplicativos sem assinatura e, por si só, não significa que o arquivo seja inseguro. Todo o código-fonte está neste repositório e o executável é gerado a partir dele com o `build.ps1` incluído e o fluxo de trabalho do GitHub Actions, então você pode revisar o código e compilar por conta própria. Baixe os arquivos somente deste repositório.
