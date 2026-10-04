import 'package:flutter_test/flutter_test.dart';
import 'package:tricycle_waste/models.dart';

void main() {
  test('pickup summary shows confirmed rubbers and price', () {
    final p = Pickup.fromJson({
      'id': 1, 'status': 'awaiting_approval', 'waste_type': 'general', 'lat': 5.6, 'lng': -0.2, 'address': null,
      'declared_units': 6, 'confirmed_units': 10, 'quoted_price': '23.00', 'proposed_price': '35.00',
      'final_price': null, 'collector_id': 2, 'collector_name': 'Kofi', 'offer_expires_at': null,
      'created_at': '2026-10-04T10:00:00',
      'items': [
        {'size_code': 'small', 'load_units': 1, 'quantity_declared': 2, 'quantity_confirmed': 2},
        {'size_code': 'large', 'load_units': 4, 'quantity_declared': 1, 'quantity_confirmed': 2},
      ],
    });
    expect(p.rubbersText, '2 small, 2 large');
    expect(p.price, 35.0);
    expect(p.isActive, isTrue);
  });

  test('server times are read as UTC', () {
    expect(parseServerTime('2026-10-04T10:00:00')!.toUtc().hour, 10);
  });
}
