!ifndef PBM_GETPOS
  !define PBM_GETPOS 0x0408
!endif
!ifndef PBM_GETRANGE
  !define PBM_GETRANGE 0x0407
!endif

Var CueInstallPercent
Var CueInstallProgressBar

Function CueSetTopStatusText
  Exch $0
  SetDetailsPrint textonly
  DetailPrint "$0"
  SetDetailsPrint listonly
  Pop $0
  Return
FunctionEnd

Function CueSetInstallPercent
  Exch $0
  IntCmp $0 0 cue_percent_nonnegative cue_percent_set_zero cue_percent_nonnegative
  cue_percent_set_zero:
    StrCpy $0 0
  cue_percent_nonnegative:
  IntCmp $0 100 cue_percent_ok cue_percent_ok cue_percent_set_hundred
  cue_percent_set_hundred:
    StrCpy $0 100
  cue_percent_ok:

  StrCmp $CueInstallPercent $0 cue_set_percent_done
  StrCpy $CueInstallPercent $0
  IntFmt $1 "Installing Cue... %d%%" $0
  Push $1
  Call CueSetTopStatusText

cue_set_percent_done:
  Pop $0
  Return
FunctionEnd

Function CueAttachInstallProgressBar
  StrCmp $CueInstallProgressBar "" 0 cue_attach_done
  FindWindow $0 "#32770" "" $HWNDPARENT
  GetDlgItem $CueInstallProgressBar $0 1004
cue_attach_done:
  Return
FunctionEnd

Function CueSyncInstallPercentFromBar
  Exch $5
  Call CueAttachInstallProgressBar
  StrCmp $CueInstallProgressBar "" cue_sync_fallback

  SendMessage $CueInstallProgressBar ${PBM_GETRANGE} 0 0 $0
  SendMessage $CueInstallProgressBar ${PBM_GETRANGE} 1 0 $1
  SendMessage $CueInstallProgressBar ${PBM_GETPOS} 0 0 $2

  IntOp $3 $0 - $1
  IntCmp $3 0 cue_sync_fallback cue_sync_range_ok cue_sync_range_ok
  cue_sync_range_ok:

  IntOp $2 $2 - $1
  IntCmp $2 0 cue_sync_pos_nonnegative cue_sync_pos_set_zero cue_sync_pos_nonnegative
  cue_sync_pos_set_zero:
    StrCpy $2 0
  cue_sync_pos_nonnegative:

  IntOp $4 $2 * 100
  IntOp $4 $4 / $3
  Push $4
  Call CueSetInstallPercent
  Goto cue_sync_done

cue_sync_fallback:
  Push $5
  Call CueSetInstallPercent

cue_sync_done:
  Pop $5
  Return
FunctionEnd

!macro CUE_SET_INSTALL_PERCENT VALUE
  Push "${VALUE}"
  Call CueSetInstallPercent
!macroend

!macro CUE_SYNC_INSTALL_PERCENT FALLBACK
  Push "${FALLBACK}"
  Call CueSyncInstallPercentFromBar
!macroend

!macro CUE_RESOURCE_PROGRESS_AFTER DEST
  !if "${DEST}" == "cue-engine-01-executables.zip"
    !insertmacro CUE_SYNC_INSTALL_PERCENT 48
  !else if "${DEST}" == "cue-engine-02-torch.zip"
    !insertmacro CUE_SYNC_INSTALL_PERCENT 62
  !else if "${DEST}" == "cue-engine-03-pyside6.zip"
    !insertmacro CUE_SYNC_INSTALL_PERCENT 64
  !else if "${DEST}" == "cue-engine-04-internal.zip"
    !insertmacro CUE_SYNC_INSTALL_PERCENT 99
  !endif
!macroend

Function CueInstallPageShow
  StrCpy $CueInstallPercent ""
  StrCpy $CueInstallProgressBar ""
  Call CueAttachInstallProgressBar
  !insertmacro CUE_SET_INSTALL_PERCENT 0
FunctionEnd

Function CueInstallPageLeave
FunctionEnd

Function CueResourceDetailPrint
  Pop $R8
  Pop $R9
  StrCmp $R9 "cue-engine-01-executables.zip" 0 crd_check2
    DetailPrint "Installing core engine (1 of 4)..."
    Goto crd_done
  crd_check2:
  StrCmp $R9 "cue-engine-02-torch.zip" 0 crd_check3
    DetailPrint "Installing speech libraries (2 of 4)..."
    Goto crd_done
  crd_check3:
  StrCmp $R9 "cue-engine-03-pyside6.zip" 0 crd_check4
    DetailPrint "Installing display libraries (3 of 4)..."
    Goto crd_done
  crd_check4:
  StrCmp $R9 "cue-engine-04-internal.zip" 0 crd_done
    DetailPrint "Installing remaining engine files (4 of 4)..."
  crd_done:
  Push $R8
  Return
FunctionEnd

!macro CUE_RESOURCE_FILE DEST SRC
  Push "${DEST}"
  Call CueResourceDetailPrint
  ; none = silent File (no "Extract:" in status bar or list); listonly restores DetailPrint to listbox only
  SetDetailsPrint none
  File /a "/oname=${DEST}" "${SRC}"
  SetDetailsPrint listonly
  !insertmacro CUE_RESOURCE_PROGRESS_AFTER "${DEST}"
!macroend

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Installing application and bundled files..."
  !insertmacro CUE_SET_INSTALL_PERCENT 0
!macroend

!macro NSIS_HOOK_AFTER_MAIN_BINARY
  !insertmacro CUE_SYNC_INSTALL_PERCENT 2
!macroend

!macro NSIS_HOOK_POSTINSTALL
  StrCpy $CueInstallPercent ""
  !insertmacro CUE_SET_INSTALL_PERCENT 100
!macroend
