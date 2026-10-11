import re

from runtime import parser, device, finish, run


def main():
    args = parser().parse_args()
    if re.search(r'[\u4e00-\u9fff]', args.text):
        raise ValueError('Parler-TTS Mini 支持英文，请使用英文评测文本。')
    import torch
    from transformers import AutoTokenizer
    from parler_tts import ParlerTTSForConditionalGeneration
    selected = device(args.device)
    model = ParlerTTSForConditionalGeneration.from_pretrained(args.checkpoint_dir, local_files_only=True).to(selected).eval()
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint_dir, local_files_only=True)
    description = args.prompt or 'A female speaker delivers clear and natural speech in a quiet recording studio.'
    description = tokenizer(description, return_tensors='pt').to(selected)
    text = tokenizer(args.text, return_tensors='pt').to(selected)
    with torch.inference_mode():
        audio = model.generate(input_ids=description.input_ids, attention_mask=description.attention_mask,
                               prompt_input_ids=text.input_ids, prompt_attention_mask=text.attention_mask,
                               max_new_tokens=min(4096, max(256, len(args.text) * 16)))
    finish(audio.detach().cpu().numpy().squeeze(), model.config.sampling_rate,
           args.output, selected, args.speed)


if __name__ == '__main__':
    run(main)
