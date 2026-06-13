import 'package:flutter_test/flutter_test.dart';

import 'package:company_brain/main.dart';

void main() {
  testWidgets('renders the empty state with suggestions', (tester) async {
    await tester.pumpWidget(const CompanyBrainApp());

    expect(find.text('Ask the company brain'), findsOneWidget);
    expect(find.text('How many active GDO customers are there?'), findsOneWidget);
  });
}
