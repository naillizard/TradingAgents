FROM nousresearch/hermes-agent:main

# Copy Hermes tool wrappers
COPY hermes_tools/ /opt/hermes_tools/

# Copy seed skills (installed via SSH, not baked into runtime)
COPY hermes_config/seed_skills/ /opt/seed_skills/

# Copy system prompt / persona
COPY hermes_config/system_prompt.md /opt/hermes_tools/system_prompt.md

# Copy one-time setup scripts (run via SSH after first deploy)
COPY scripts/ /opt/scripts/

# Copy dashboard
COPY dashboard/ /opt/dashboard/

# No secrets, no credentials — all injected at runtime via fly secrets set
