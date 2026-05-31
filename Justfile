set shell := ["bash", "-c"]

ROOT := `pwd`
TEMPLATE := "doc_template.html"

# Top-level orchestrator for multi-project docs rendering.
default:
  @just --list

check-template:
  @test -f "{{ROOT}}/{{TEMPLATE}}" || (echo "Missing {{TEMPLATE}} at repo root" && exit 1)
  @echo "✓ Found canonical template: {{ROOT}}/{{TEMPLATE}}"

building-ai-html: check-template
  cd building_ai_agents && just main-html

building-ai-docs: check-template
  cd building_ai_agents && just docs

political-html: check-template
  cd political_systems && just docs

numerical-html: check-template
  cd numerical_analysis_primer && just html

openclaw-html: check-template
  cd openclaw_primer && ./render.sh

claude-alt-html: check-template
  cd claude_code_alternative && just html

claude-alt-pdf: check-template
  cd claude_code_alternative && just pdf

claude-alt-docs: check-template
  cd claude_code_alternative && just all

research-html: check-template
  cd research_local_llms && ./render.sh

catmodel-html-dev: check-template
  cd catmodel_elt_documents && just render-dev-container

catmodel-html-full: check-template
  cd catmodel_elt_documents && just render-full-container

# Common daily build across active document projects.
html-dev: building-ai-html building-ai-docs political-html numerical-html openclaw-html research-html catmodel-html-dev claude-alt-html
  @echo "✓ Dev HTML render complete across projects"

# Full render where supported.
html-full: building-ai-html building-ai-docs political-html numerical-html openclaw-html research-html catmodel-html-full claude-alt-docs
  @echo "✓ Full HTML render complete across projects"

clean-generated:
  cd building_ai_agents && just clean
  cd political_systems && just clean
  cd numerical_analysis_primer && just clean
  rm -f openclaw_primer/openclaw_primer.html openclaw_primer/openclaw_primer.pdf
  rm -f research_local_llms/running-llms-locally.html research_local_llms/running-llms-locally.pdf
  cd catmodel_elt_documents && just clean
  cd claude_code_alternative && just clean
  @echo "✓ Generated artifacts cleaned"
