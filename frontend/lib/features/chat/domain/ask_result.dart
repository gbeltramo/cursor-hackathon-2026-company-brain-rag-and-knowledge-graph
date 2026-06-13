/// The parsed response from the backend `POST /ask` endpoint.
class AskResult {
  const AskResult({
    required this.answer,
    required this.sources,
    required this.verticale,
    this.artifactUrl,
  });

  final String answer;
  final List<String> sources;
  final String verticale;
  final String? artifactUrl;

  factory AskResult.fromJson(Map<String, dynamic> json) {
    final rawSources = json['sources'];
    return AskResult(
      answer: (json['answer'] as String?)?.trim() ?? '',
      sources: rawSources is List
          ? rawSources.map((e) => e.toString()).toList(growable: false)
          : const <String>[],
      verticale: (json['verticale'] as String?) ?? 'kb',
      artifactUrl: (json['artifact_url'] as String?),
    );
  }
}
