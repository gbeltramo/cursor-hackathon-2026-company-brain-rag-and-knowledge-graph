import 'package:flutter/material.dart';
import 'package:flutter_widget_from_html_core/flutter_widget_from_html_core.dart';
import 'package:markdown/markdown.dart' as md;
import 'package:url_launcher/url_launcher.dart';

import '../../domain/ask_result.dart';

/// Renders a successful [AskResult]: the answer body, the verticale tag, the
/// list of sources, and a download button for any binary artifact.
class AnswerView extends StatelessWidget {
  const AnswerView({super.key, required this.result});

  final AskResult result;

  static final RegExp _htmlTag =
      RegExp(r'<(html|body|div|section|table|h[1-6]|p|ul|ol|li|head|style)\b',
          caseSensitive: false);

  bool get _looksLikeHtml => _htmlTag.hasMatch(result.answer);

  /// The answer rendered as HTML. Plain answers are treated as Markdown and
  /// converted, so **bold**, lists, tables and `code` look polished instead of
  /// showing raw markers.
  String get _html => _looksLikeHtml
      ? result.answer
      : md.markdownToHtml(
          result.answer,
          extensionSet: md.ExtensionSet.gitHubFlavored,
        );

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _VerticaleTag(verticale: result.verticale),
        const SizedBox(height: 8),
        SelectionArea(
          child: HtmlWidget(
            _html,
            textStyle: theme.textTheme.bodyLarge?.copyWith(height: 1.5),
            onTapUrl: (url) async {
              final uri = Uri.tryParse(url);
              if (uri == null) return false;
              await launchUrl(uri, webOnlyWindowName: '_blank');
              return true;
            },
          ),
        ),
        if (result.artifactUrl != null) ...[
          const SizedBox(height: 12),
          _ArtifactButton(url: result.artifactUrl!),
        ],
        if (result.sources.isNotEmpty) ...[
          const SizedBox(height: 14),
          _Sources(sources: result.sources),
        ],
      ],
    );
  }
}

class _VerticaleTag extends StatelessWidget {
  const _VerticaleTag({required this.verticale});

  final String verticale;

  static const Map<String, IconData> _icons = {
    'crm': Icons.people_alt_outlined,
    'erp': Icons.factory_outlined,
    'calls': Icons.call_outlined,
    'kb': Icons.menu_book_outlined,
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_icons[verticale] ?? Icons.help_outline,
              size: 14, color: theme.colorScheme.onPrimaryContainer),
          const SizedBox(width: 6),
          Text(
            verticale.toUpperCase(),
            style: theme.textTheme.labelMedium?.copyWith(
              color: theme.colorScheme.onPrimaryContainer,
              letterSpacing: 1.2,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _Sources extends StatelessWidget {
  const _Sources({required this.sources});

  final List<String> sources;

  /// Knowledge-base document ids (e.g. "DOC-004") can be opened as plain text;
  /// API endpoints (e.g. "crm/opportunities") are shown as static chips.
  static final RegExp _docId = RegExp(r'^DOC-\d+$', caseSensitive: false);

  /// Plain-text URL for a KB document, served by the backend on the same
  /// origin as the web app.
  Uri _docUri(String id) => Uri.base.resolve('kb/${id.toUpperCase()}');

  Future<void> _open(String id) async {
    await launchUrl(_docUri(id), webOnlyWindowName: '_blank');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Sources',
          style: theme.textTheme.labelLarge?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            for (final s in sources)
              if (_docId.hasMatch(s.trim()))
                ActionChip(
                  onPressed: () => _open(s.trim()),
                  avatar: Icon(
                    Icons.open_in_new,
                    size: 15,
                    color: theme.colorScheme.primary,
                  ),
                  label: Text(s),
                  tooltip: 'Open ${s.toUpperCase()} as plain text',
                  visualDensity: VisualDensity.compact,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  side: BorderSide(color: theme.colorScheme.outlineVariant),
                )
              else
                Chip(
                  label: SelectableText(s),
                  visualDensity: VisualDensity.compact,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  side: BorderSide(color: theme.colorScheme.outlineVariant),
                ),
          ],
        ),
      ],
    );
  }
}

class _ArtifactButton extends StatelessWidget {
  const _ArtifactButton({required this.url});

  final String url;

  Future<void> _open() async {
    final uri = Uri.tryParse(url);
    if (uri != null) {
      await launchUrl(uri, webOnlyWindowName: '_blank');
    }
  }

  @override
  Widget build(BuildContext context) {
    return FilledButton.tonalIcon(
      onPressed: _open,
      icon: const Icon(Icons.download_outlined, size: 18),
      label: const Text('Open generated file'),
    );
  }
}
