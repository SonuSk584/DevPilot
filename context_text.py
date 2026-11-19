from app.service.context_builder import build_repository_context

repository_path = "/home/sonu/DevPilot"

context = build_repository_context(repository_path)

print("Repository context generated successfully!")
print(f"Total characters: {len(context)}")

print("\nPreview:")
print(context[:3000])