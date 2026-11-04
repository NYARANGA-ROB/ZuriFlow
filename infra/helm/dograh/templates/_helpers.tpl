{{/*
Dograh Helm helpers
*/}}
{{- define "dograh.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "dograh.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "dograh.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end }}

{{- define "dograh.labels" -}}
helm.sh/chart: {{ include "dograh.chart" . }}
{{ include "dograh.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "dograh.selectorLabels" -}}
app.kubernetes.io/name: {{ include "dograh.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "dograh.api.selectorLabels" -}}
{{ include "dograh.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{- define "dograh.worker.selectorLabels" -}}
{{ include "dograh.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{- define "dograh.ui.selectorLabels" -}}
{{ include "dograh.selectorLabels" . }}
app.kubernetes.io/component: ui
{{- end }}

{{- define "dograh.gpuWorker.selectorLabels" -}}
{{ include "dograh.selectorLabels" . }}
app.kubernetes.io/component: gpu-worker
{{- end }}

{{- define "dograh.image" -}}
{{- $registry := .global.imageRegistry -}}
{{- $repo := .repository -}}
{{- $tag := .tag | default .defaultTag -}}
{{- if $registry -}}
{{ printf "%s/%s:%s" $registry $repo $tag }}
{{- else -}}
{{ printf "%s:%s" $repo $tag }}
{{- end -}}
{{- end }}

{{- define "dograh.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- include "dograh.fullname" . }}-secrets
{{- end }}
{{- end }}

{{- define "dograh.databaseUrl" -}}
{{- if .Values.postgresql.external.enabled -}}
{{- else -}}
{{- $pw := .Values.postgresql.auth.password | default .Values.secrets.postgresPassword -}}
postgresql+asyncpg://{{ .Values.postgresql.auth.username }}:{{ $pw | urlquery }}@{{ include "dograh.fullname" . }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- end -}}
{{- end }}

{{- define "dograh.redisUrl" -}}
{{- if .Values.redis.external.enabled -}}
{{- else -}}
{{- $pw := .Values.redis.auth.password | default .Values.secrets.redisPassword -}}
redis://:{{ $pw | urlquery }}@{{ include "dograh.fullname" . }}-redis:6379
{{- end -}}
{{- end }}
