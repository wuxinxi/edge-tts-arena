export const englishExample = 'Welcome to the voice assistant. Your order will arrive tomorrow afternoon. Please check your notifications.'

// Detect unsupported scripts, not the language of Latin-script text. Never translate benchmark inputs.
export function textCompatibilityError(keys: string[], texts: string[]): string {
  if (!keys.includes('parler-tts-mini')) return ''
  const unsupported = texts.some(text => Array.from(text).some(character =>
    /\p{Letter}/u.test(character) && !/\p{Script=Latin}/u.test(character)))
  return unsupported ? 'Parler-TTS Mini v1 仅支持英文。请选择英文文本，或取消该模型；评测不会自动翻译正文。' : ''
}

export function compatibleModelKeys(keys: string[], texts: string[]): string[] {
  return keys.filter(key => !textCompatibilityError([key], texts))
}
