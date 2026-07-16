# Format Support Notes

Use these notes to set expectations before converting project files.

## Reliable Interchange Layer

The skill preserves:

- Timeline cut/event start, end, duration, and track labels.
- Clip/source names and paths when present.
- Subtitle/title text and timing.
- Basic frame rate and duration metadata.

The skill does not claim lossless transfer of:

- Effects, transitions, color, masks, keyframes, speed ramps, multicam structure, compound clips, generators, audio automation, motion graphics, app-specific metadata, or media relinking.

## App Notes

- Final Cut Pro: FCPXML is Apple's interchange format for sending data between Final Cut Pro and third-party tools. Prefer `.fcpxml` or `.fcpxmld` bundle input/output.
- Premiere Pro: Adobe's current guidance is to import FCP7-style XML; modern FCPXML from Final Cut Pro X needs conversion before Premiere can directly import it. Premiere can export Final Cut Pro XML, but not every effect or feature transfers.
- DaVinci Resolve: Resolve commonly imports XML, FCPXML, AAF, and EDL timelines. Use FCPXML and EDL exports as the practical bridge unless Resolve scripting is available and the user specifically needs a native project operation.
- CapCut/Jianying: `draft_content.json` and related files are undocumented by ByteDance and change by app version. Treat generated draft JSON as best-effort unless patching a user-supplied template draft from the same version.

## Source Links

- Apple Final Cut Pro XML reference: https://developer.apple.com/documentation/professional-video-applications/fcpxml-reference
- Apple Final Cut Pro XML transfer guide: https://support.apple.com/guide/final-cut-pro/use-xml-to-transfer-projects-verdbd66ae/mac
- Adobe Premiere Pro FCPX XML import guidance: https://helpx.adobe.com/premiere/desktop/organize-media/import-files/migrate-from-final-cut-pro-x.html
- Adobe Premiere Pro Final Cut Pro XML export guidance: https://helpx.adobe.com/ee/premiere/desktop/render-and-export/export-files/export-a-project-as-a-final-cut-pro-xml-file.html
- Blackmagic Resolve 18.6 notes mentioning XML/AAF/FCPXML/EDL import and FCPXML 1.11 support: https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_18.6_New_Features_Guide.pdf
- Unofficial CapCut/Jianying draft schema reference: https://app.unpkg.com/capcut-cli%400.12.0/files/docs/draft-schema/README.md
