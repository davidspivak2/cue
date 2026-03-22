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
    checkMissedSpeech: "Making sure no words were missed",
    matchWords: "Building word-by-word karaoke effect",
    preparingPreview: "Preparing preview"
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
  preparingPreview: "preparing_preview"
} as const;

export type ChecklistStepId = (typeof checklistStepIds)[keyof typeof checklistStepIds];

export type ChecklistOptions = {
  apply_audio_filter?: boolean;
  punctuation_rescue_fallback_enabled?: boolean;
  vad_gap_rescue_enabled?: boolean;
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

  items.push({ id: checklistStepIds.timingWordHighlights, label: labels.matchWords });
  items.push({ id: checklistStepIds.preparingPreview, label: labels.preparingPreview });
  return items;
};
