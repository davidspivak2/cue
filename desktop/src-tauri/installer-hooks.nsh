!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Installing Cue app files..."
  DetailPrint "Installing the local subtitle engine. This is the longest step and may take a few minutes."
  DetailPrint "Cue includes its speech and video tools in this step so it can work offline after setup."
!macroend

!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "Setup finished copying Cue."
  DetailPrint "The first time you open Cue, it will finish preparing the local engine for this Windows account."
!macroend
