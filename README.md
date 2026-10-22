# KOReader Reading Recap

Return to a book with a short recap of what you have already read, including the questions still open at your reading position.

This project has two parts: a KOReader plugin exports text up to the current reading position, and a Windows companion uses **your own AI account** to generate and deliver a recap when the reader is connected over USB. Choose a signed-in Codex CLI, or your own OpenAI, Anthropic, or Google Gemini API key. New recaps are offered once when opening or resuming a book and remain available from the reader menu.

## Status

Early working release, tested on a jailbroken Kindle running KOReader **v2026.07.1** and a Windows laptop. Other KOReader devices and versions have not been tested. The companion currently supports Windows only. The reader exporter supports book EPUBs. It does not include books, a jailbreak, or instructions to remove DRM.

The interface and generated recaps are currently **German**. Each recap has four sections: setting, story so far, main characters, and open questions at your reading position. Non-fiction uses key ideas and concepts instead of plot and characters.

## Requirements

- A device with KOReader installed and its `koreader` directory accessible over USB.
- Windows and Python **3.11 or later**, available as `python`.
- Either the official [Codex CLI](https://developers.openai.com/codex/cli/) signed in with your own account (`codex login`), **or** your own API key for one of the providers below. Codex is not required in API mode.
- Internet access and available allowance/API billing for your chosen provider. Codex mode requires a modern CLI with `exec --ephemeral --output-schema --ignore-user-config`. API mode uses Python's standard library and needs no provider SDK.

## Choose your AI provider

Run this once before the first sync (or again to change provider/model/key):

```powershell
.\companion\configure.ps1
```

Choose `codex`, `openai`, `anthropic`, or `gemini`. For an API provider, enter the exact model ID from your account and then paste your API key at the hidden prompt. Choose a text model with sufficient context for approximately 60,000 source characters plus an earlier recap (at least 32k context is a useful starting point; tokenization varies). OpenAI models must support Chat Completions and JSON mode. No particular model is hardcoded, since availability depends on your account and changes over time.

| Selection | Account/key | Request API |
|---|---|---|
| `codex` (default) | Your signed-in Codex CLI | Non-interactive Codex; no API key required |
| `openai` | [OpenAI API keys](https://platform.openai.com/api-keys) | [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) |
| `anthropic` | [Anthropic Console](https://platform.claude.com/) | [Messages API](https://platform.claude.com/docs/en/api/messages/create) |
| `gemini` | [Google AI Studio API keys](https://aistudio.google.com/apikey) | [GenerateContent](https://ai.google.dev/api/generate-content) |

Chat subscriptions do not automatically provide API billing or credit. Check model access, pricing and limits with your chosen provider. Requests are capped at 4,096 output tokens for Anthropic and 8,192 for OpenAI/Gemini; these are upper bounds, not targets. The source is processed in chunks, so long first reads can make multiple paid calls.

The setup stores `provider.json` in `%LOCALAPPDATA%\KOReaderReadingRecap`, **outside the repository**. The key is encrypted using Windows DPAPI for the current Windows user; moving this file to another computer/account will not provide a working key. Re-run setup there. This protects storage, but does not protect against programs already running as you. Setup does not make a paid test call. The existing USB task automatically uses this configuration on its next run under the same Windows user.

Advanced users can instead set `RECAP_PROVIDER`, `RECAP_MODEL` and the matching `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY` in the environment of the sync process. Environment values take precedence. In API mode a missing key/model is an error: the helper never silently switches to Codex or another provider. With no configuration, Codex remains the default. Switching provider or model regenerates affected recaps from their bounded source; it can incur new API usage.

## Install

1. Download this repository using **Code → Download ZIP**, then extract it to a permanent folder on your laptop.
2. Connect your reader over USB.
3. Copy the entire `readingrecap.koplugin` folder into the reader's `koreader/plugins/` directory.
4. Safely eject the reader and restart KOReader. If needed, enable **Leserückblick** in plugin management.
5. Open a book EPUB, read, and close the book before connecting over USB again. The first connection before this step has no reading exports to process.
6. In PowerShell, from this repository folder, run:

   ```powershell
   .\companion\sync.ps1
   ```

   The script detects connected readers by the installed plugin. To choose one explicitly:

   ```powershell
   .\companion\sync.ps1 -Device 'F:\'
   ```

   If PowerShell blocks local scripts, review the script and use a process-only policy for this invocation (the same form works for `configure.ps1`):

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\companion\sync.ps1
   ```

7. Keep the reader connected until the script finishes. Safely eject it and open the book. Choose **Rückblick lesen**. The same action is available from KOReader's reader menu.

### Run automatically on USB connection

After completing one manual round trip, run:

```powershell
.\companion\install-usb-task.ps1
```

This creates a Windows task named **KOReader-Reading-Recap** for the current signed-in user. It waits 20 seconds after a Windows Partition/Diagnostic event 1006 and checks for connected readers. Event availability can vary by Windows installation; if it does not fire, the manual command still works. Leave this repository in its installation location. The task runs only while you are signed in. Completion and errors are written to `companion/sync.log`.

Do not register this additional task if an existing backup job already calls `recap_sync.py`; add the invocation to that job instead. Duplicate companion invocations are serialized by a process lock.

## Privacy and limitations

- **Read text is sent to your selected provider**: OpenAI for Codex/OpenAI API mode, Anthropic for Claude API mode, or Google for Gemini. Generation uses your Codex allowance or API billing. Long first reads may require multiple calls. Subsequent forward reading can reuse the earlier recap and summarize only additional text. A failed request is retried only on a later sync; automatic immediate retries are not made.
- KOReader exports from the first page to the current text position using its own XPointer functions. This avoids estimating a text boundary from percentages. It is **not a guarantee against spoilers or AI mistakes**: front matter can itself reveal plot, and a language model may infer or invent details.
- Skipping forward is treated as reaching that position, even if you did not read the intervening pages. A prepared recap is hidden if you move back before its boundary.
- Each newly opened/read session can produce a new delivered revision. If the text has not changed, the companion reuses the summary without another AI call. An identical repeated connection does nothing.
- On failed generation or delivery the existing recap is retained; the next connection retries. Do not disconnect during generation. A book not exported by KOReader cannot be updated.
- Requests contain the read text, book title, reading position, and activity metadata. They remain on the reader under `koreader/settings/reading_recap_requests/`. Replies are in `reading_recaps/`. Companion state and summaries are in `companion/recap-cache/`; failure diagnostics can also contain private information. Your backup system may copy these files. **Do not upload any of them.** This repository ignores runtime files and contains synthetic test data only.
- Export limit: 4 million text characters in the companion. Oversized requests fail rather than being silently truncated. Reflowable EPUBs only; KFX and AZW3 are not exported.

## Tests

No network, real API keys, or paid allowance is used by these tests:

```powershell
python -m unittest discover -s companion -p 'test_*.py'
```

They cover provider request formats/authentication, truncated/error responses, no-Codex API sync, provider switching, Windows key encryption/decryption with a synthetic key, required sections, old-format cache migration, incremental and backwards reading, repeated sync, delivery retry, multiple books, request validation and chunk coverage. The Windows encryption test writes only temporary configuration and does not change your saved settings. API requests are mocked: the new API backends have not been live-tested with billed credentials. The Lua plugin has also been tested with a local LuaJIT mock harness during development; that harness is not included in this first package. Real-device testing remains necessary for other devices and KOReader versions.

## Uninstall

Disable **Leserückblick** in KOReader plugin management and restart KOReader. To remove the automatic Windows task:

```powershell
Unregister-ScheduledTask -TaskName 'KOReader-Reading-Recap' -Confirm:$false
```

Runtime data is left in place so uninstalling does not discard your recaps. Remove those private data directories separately if you want to erase them.

## License

Original project code is licensed under AGPL-3.0-or-later; see [COPYING](COPYING). KOReader is a separate project and is not bundled here. This project is not affiliated with KOReader or OpenAI.
