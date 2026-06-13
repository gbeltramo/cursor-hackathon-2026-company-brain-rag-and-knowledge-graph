import 'package:flutter/material.dart';
import 'package:flutter_widget_from_html_core/flutter_widget_from_html_core.dart';
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

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _VerticaleTag(verticale: result.verticale),
        const SizedBox(height: 8),
        if (_looksLikeHtml)
          SelectionArea(child: HtmlWidget(result.answer))
        else
          SelectableText(
            result.answer,
            style: theme.textTheme.bodyLarge?.copyWith(height: 1.5),
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

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SelectableText(
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
