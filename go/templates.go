package llmclient

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// PromptTemplate holds a named prompt with optional system and user parts.
type PromptTemplate struct {
	Name           string
	UserTemplate   string
	SystemTemplate string
}

// Render replaces {key} placeholders with the provided variables.
func (t *PromptTemplate) Render(vars map[string]string) (user, system string, err error) {
	user, err = renderTemplate(t.UserTemplate, vars)
	if err != nil {
		return
	}
	if t.SystemTemplate != "" {
		system, err = renderTemplate(t.SystemTemplate, vars)
	}
	return
}

var placeholderRe = regexp.MustCompile(`\{(\w+)\}`)

func renderTemplate(tmpl string, vars map[string]string) (string, error) {
	var missing []string
	result := placeholderRe.ReplaceAllStringFunc(tmpl, func(match string) string {
		key := match[1 : len(match)-1]
		if val, ok := vars[key]; ok {
			return val
		}
		missing = append(missing, key)
		return match
	})
	if len(missing) > 0 {
		return "", fmt.Errorf("missing template variables: %v", missing)
	}
	return result, nil
}

// TemplateRegistry stores and retrieves PromptTemplates.
type TemplateRegistry struct {
	registry map[string]*PromptTemplate
}

// NewTemplateRegistry creates an empty registry.
func NewTemplateRegistry() *TemplateRegistry {
	return &TemplateRegistry{registry: make(map[string]*PromptTemplate)}
}

// Register adds a template by name.
func (r *TemplateRegistry) Register(name, userTmpl, systemTmpl string) {
	r.registry[name] = &PromptTemplate{
		Name:           name,
		UserTemplate:   strings.TrimSpace(userTmpl),
		SystemTemplate: strings.TrimSpace(systemTmpl),
	}
}

// LoadDir scans a directory for *.txt files and registers each as a template.
func (r *TemplateRegistry) LoadDir(dir string) (int, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0, err
	}
	count := 0
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".txt") {
			continue
		}
		name := strings.TrimSuffix(e.Name(), ".txt")
		raw, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			return count, err
		}
		r.registry[name] = parseTemplateFile(name, string(raw))
		count++
	}
	return count, nil
}

// Get retrieves a template by name or returns TemplateNotFoundError.
func (r *TemplateRegistry) Get(name string) (*PromptTemplate, error) {
	t, ok := r.registry[name]
	if !ok {
		return nil, &TemplateNotFoundError{
			LLMError:     LLMError{Message: fmt.Sprintf("template not found: %q", name)},
			TemplateName: name,
		}
	}
	return t, nil
}

// List returns all registered template names.
func (r *TemplateRegistry) List() []string {
	names := make([]string, 0, len(r.registry))
	for k := range r.registry {
		names = append(names, k)
	}
	return names
}

// ChatWithTemplate renders the named template and calls the LLM.
func (r *TemplateRegistry) ChatWithTemplate(
	ctx context.Context,
	c *Client,
	templateName string,
	vars map[string]string,
	opts *ChatOpts,
) (string, error) {
	tmpl, err := r.Get(templateName)
	if err != nil {
		return "", err
	}
	userPrompt, systemPrompt, err := tmpl.Render(vars)
	if err != nil {
		return "", err
	}
	if opts == nil {
		opts = &ChatOpts{}
	}
	opts.System = systemPrompt
	return c.Chat(ctx, userPrompt, opts)
}

func parseTemplateFile(name, content string) *PromptTemplate {
	content = strings.TrimSpace(content)
	sysRe := regexp.MustCompile(`(?i)^system:\s*`)
	if sysRe.MatchString(content) {
		parts := strings.SplitN(content, "\n---\n", 2)
		if len(parts) == 2 {
			systemText := strings.TrimSpace(sysRe.ReplaceAllString(parts[0], ""))
			return &PromptTemplate{
				Name:           name,
				UserTemplate:   strings.TrimSpace(parts[1]),
				SystemTemplate: systemText,
			}
		}
	}
	return &PromptTemplate{Name: name, UserTemplate: content}
}
