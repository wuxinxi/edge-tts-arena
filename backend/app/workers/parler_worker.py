from runtime import parser, device, finish, run
from worker_settings import parler_description, seed_generation, validate_parler_text


def main():
    args = parser().parse_args()
    validate_parler_text(args.text)
    import torch
    from transformers import AutoTokenizer
    from parler_tts import ParlerTTSForConditionalGeneration
    selected = device(args.device)
    model = ParlerTTSForConditionalGeneration.from_pretrained(args.checkpoint_dir, local_files_only=True).to(selected).eval()
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint_dir, local_files_only=True)
    seed = seed_generation(args.options)
    effective_description = parler_description(args.prompt, args.voice)
    description = tokenizer(effective_description, return_tensors='pt').to(selected)
    text = tokenizer(args.text, return_tensors='pt').to(selected)
    with torch.inference_mode():
        audio = model.generate(input_ids=description.input_ids, attention_mask=description.attention_mask,
                               prompt_input_ids=text.input_ids, prompt_attention_mask=text.attention_mask,
                               max_new_tokens=min(4096, max(256, len(args.text) * 16)))
    finish(audio.detach().cpu().numpy().squeeze(), model.config.sampling_rate,
           args.output, selected, args.speed,
           dict(args.options, seed=seed, language='English', speaker=args.voice,
                description=effective_description, precision=str(next(model.parameters()).dtype)))


if __name__ == '__main__':
    run(main)
