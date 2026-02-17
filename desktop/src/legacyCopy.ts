export const legacyCopy = {
  dropZone: {
    headline: "Drop a video here",
    subtext: "or choose one from your computer",
    chooseButton: "Choose video..."
  },
  videoCard: {
    placeholder: "Preview not available",
    remove: "Remove video"
  },
  videoSelected: {
    cta: "Create subtitles"
  },
  working: {
    createSubtitlesHeading: "Creating subtitles",
    createVideoHeading: "Creating video with subtitles",
    cancel: "Cancel"
  },
  subtitlesReady: {
    header: "Subtitles created",
    footerPrefix: "Saving as:",
    cta: "Export"
  },
  done: {
    header: "Your video is ready",
    playVideo: "Play video",
    openFolder: "Open folder"
  },
  settings: {
    back: "Back"
  },
  progress: {
    elapsedPrefix: "Elapsed:"
  },
  checklistLabels: {
    extractAudio: "Extracting audio",
    extractAudioFiltered: "Extracting and cleaning up audio",
    loadModel: "Loading AI model",
    detectLanguage: "Detecting language",
    writeSubtitles: "Writing subtitles",
    reviewPunctuation: "Reviewing punctuation",
    checkMissedSpeech: "Checking for missed speech",
    matchWords: "Matching individual words to speech",
    preparingPreview: "Preparing preview",
    getVideoInfo: "Getting video info",
    addSubtitles: "Adding subtitles to video",
    saveVideo: "Saving video"
  }
} as const;

export const checklistStepIds = {
  extractAudio: "extract_audio",
  loadModel: "load_model",
  detectLanguage: "detect_language",
  writeSubtitles: "write_subtitles",
  fixPunctuation: "fix_punctuation",
  fixMissingSubtitles: "fix_missing_subtitles",
  timingWordHighlights: "timing_word_highlights",
  preparingPreview: "preparing_preview",
  getVideoInfo: "get_video_info",
  addSubtitles: "add_subtitles",
  saveVideo: "save_video"
} as const;

export type ChecklistStepId = (typeof checklistStepIds)[keyof typeof checklistStepIds];

export type ChecklistOptions = {
  apply_audio_filter?: boolean;
  punctuation_rescue_fallback_enabled?: boolean;
  vad_gap_rescue_enabled?: boolean;
  subtitle_mode?: string;
};

export type ChecklistDefinition = {
  id: ChecklistStepId;
  label: string;
};

export const buildGenerateChecklist = (
  options: ChecklistOptions = {}
): ChecklistDefinition[] => {
  const labels = legacyCopy.checklistLabels;
  const useAudioFilter = options.apply_audio_filter !== false;
  const includePunctuation = options.punctuation_rescue_fallback_enabled !== false;
  const includeGapRescue = options.vad_gap_rescue_enabled !== false;
  const isWordHighlight = options.subtitle_mode === "word_highlight";

  const items: ChecklistDefinition[] = [
    {
      id: checklistStepIds.extractAudio,
      label: useAudioFilter ? labels.extractAudioFiltered : labels.extractAudio
    },
    { id: checklistStepIds.loadModel, label: labels.loadModel },
    { id: checklistStepIds.detectLanguage, label: labels.detectLanguage },
    { id: checklistStepIds.writeSubtitles, label: labels.writeSubtitles }
  ];

  if (includePunctuation) {
    items.push({ id: checklistStepIds.fixPunctuation, label: labels.reviewPunctuation });
  }

  if (includeGapRescue) {
    items.push({ id: checklistStepIds.fixMissingSubtitles, label: labels.checkMissedSpeech });
  }

  if (isWordHighlight) {
    items.push({ id: checklistStepIds.timingWordHighlights, label: labels.matchWords });
  }

  items.push({ id: checklistStepIds.preparingPreview, label: labels.preparingPreview });
  return items;
};

export const buildExportChecklist = (): ChecklistDefinition[] => {
  const labels = legacyCopy.checklistLabels;
  return [
    { id: checklistStepIds.getVideoInfo, label: labels.getVideoInfo },
    { id: checklistStepIds.addSubtitles, label: labels.addSubtitles },
    { id: checklistStepIds.saveVideo, label: labels.saveVideo }
  ];
};
