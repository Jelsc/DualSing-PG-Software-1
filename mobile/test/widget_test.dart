import 'package:flutter_test/flutter_test.dart';
import 'package:dualsign_mobile/main.dart';

void main() {
  testWidgets('renders the minimal mobile shell', (WidgetTester tester) async {
    await tester.pumpWidget(const DualSignMobileApp());

    expect(find.text('DualSign Mobile'), findsOneWidget);
    expect(find.text('Mobile shell for Phase 0.'), findsOneWidget);
  });
}
