# GoW Overlay

[English](#english) | [Português](#português)

## English

GoW Overlay is a Windows utility that combines a Twitch chat overlay with automatic OBS display-capture control. It was originally created for crash-free *God of War* speedruns, particularly on systems where the OBS Game Capture hook may cause instability, and was later expanded for single-monitor and smaller-screen setups.

### Features

- Displays Twitch chat over the game without using the OBS Game Capture hook.
- Supports Twitch emotes, including animated emotes.
- Shows channel-point redemptions and subscription activity.
- Automatically enables or disables an OBS display-capture source according to the active window.
- Can operate as chat only, OBS control only or both.
- Supports multiple monitors and proportionally scales the overlay from a 1920×1080 reference layout.
- Includes configurable font, opacity, spacing, dimensions, position and message behavior.
- Keeps the Settings and Live Control windows out of OBS capture when supported by Windows.

### Requirements

- Windows 10 or Windows 11
- OBS Studio with WebSocket enabled on port `4455` and no password
- A Twitch account for chat, redemption and subscription authorization
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

`tokens.txt` and `config.json` are excluded from the repository through `.gitignore`.

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
- Suporta emotes da Twitch, incluindo emotes animados.
- Exibe resgates de pontos do canal e atividades de inscrições.
- Ativa ou desativa automaticamente uma fonte de captura de tela do OBS conforme a janela em foco.
- Pode funcionar somente com o chat, somente com o controle do OBS ou com os dois recursos juntos.
- Suporta vários monitores e redimensiona proporcionalmente o overlay a partir de um layout-base de 1920×1080.
- Permite configurar fonte, opacidade, espaçamento, dimensões, posição e comportamento das mensagens.
- Mantém as janelas de Configurações e Live Control fora da captura do OBS quando o Windows oferece suporte.

### Requisitos

- Windows 10 ou Windows 11
- OBS Studio com o WebSocket ativado na porta `4455` e sem senha
- Uma conta da Twitch para autorizar a leitura do chat, resgates e inscrições
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

Os arquivos `tokens.txt` e `config.json` são excluídos do repositório pelo `.gitignore`.

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
