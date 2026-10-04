double _num(dynamic v) => v == null ? 0 : double.tryParse(v.toString()) ?? 0;
double? _numOrNull(dynamic v) => v == null ? null : double.tryParse(v.toString());

/// The server sends times in UTC without a time zone marker.
DateTime? parseServerTime(dynamic v) {
  if (v == null) return null;
  final s = v.toString();
  return DateTime.tryParse(s.endsWith('Z') ? s : '${s}Z')?.toLocal();
}

class RubberSize {
  RubberSize.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        code = j['code'] as String,
        name = j['name'] as String,
        description = j['description'] as String,
        loadUnits = j['load_units'] as int;

  final int id;
  final String code;
  final String name;
  final String description;
  final int loadUnits;
}

class Quote {
  Quote.fromJson(Map<String, dynamic> j)
      : totalUnits = j['total_units'] as int,
        baseFee = _num(j['base_fee']),
        unitsCharge = _num(j['units_charge']),
        distanceCharge = _num(j['distance_charge']),
        total = _num(j['total']),
        distanceKm = _numOrNull(j['distance_km']),
        collectorsAvailable = j['collectors_available'] as int;

  final int totalUnits;
  final double baseFee;
  final double unitsCharge;
  final double distanceCharge;
  final double total;
  final double? distanceKm;
  final int collectorsAvailable;
}

class PickupItem {
  PickupItem.fromJson(Map<String, dynamic> j)
      : sizeCode = j['size_code'] as String,
        loadUnits = j['load_units'] as int,
        quantityDeclared = j['quantity_declared'] as int,
        quantityConfirmed = j['quantity_confirmed'] as int?;

  final String sizeCode;
  final int loadUnits;
  final int quantityDeclared;
  final int? quantityConfirmed;
}

class Pickup {
  Pickup.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        status = j['status'] as String,
        wasteType = j['waste_type'] as String,
        lat = _num(j['lat']),
        lng = _num(j['lng']),
        address = j['address'] as String?,
        declaredUnits = j['declared_units'] as int,
        confirmedUnits = j['confirmed_units'] as int?,
        quotedPrice = _num(j['quoted_price']),
        proposedPrice = _numOrNull(j['proposed_price']),
        finalPrice = _numOrNull(j['final_price']),
        collectorName = j['collector_name'] as String?,
        offerExpiresAt = parseServerTime(j['offer_expires_at']),
        createdAt = parseServerTime(j['created_at']) ?? DateTime.now(),
        items = (j['items'] as List).map((e) => PickupItem.fromJson(Map<String, dynamic>.from(e as Map))).toList();

  final int id;
  final String status;
  final String wasteType;
  final double lat;
  final double lng;
  final String? address;
  final int declaredUnits;
  final int? confirmedUnits;
  final double quotedPrice;
  final double? proposedPrice;
  final double? finalPrice;
  final String? collectorName;
  final DateTime? offerExpiresAt;
  final DateTime createdAt;
  final List<PickupItem> items;

  bool get isActive => const ['searching', 'offered', 'accepted', 'awaiting_approval', 'collected'].contains(status);
  double get price => finalPrice ?? proposedPrice ?? quotedPrice;

  String get rubbersText => items
      .map((i) => (i.quantityConfirmed ?? i.quantityDeclared, i.sizeCode))
      .where((t) => t.$1 > 0)
      .map((t) => '${t.$1} ${t.$2}')
      .join(', ');
}

class DisposalSite {
  DisposalSite.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        name = j['name'] as String,
        lat = _num(j['lat']),
        lng = _num(j['lng']),
        radiusM = _num(j['radius_m']);

  final int id;
  final String name;
  final double lat;
  final double lng;
  final double radiusM;
}

class LoadInfo {
  LoadInfo.fromJson(Map<String, dynamic> j)
      : capacityUnits = j['capacity_units'] as int,
        loadUnits = j['load_units'] as int,
        reservedUnits = j['reserved_units'] as int,
        availableUnits = j['available_units'] as int,
        fillPercent = _num(j['fill_percent']),
        status = j['status'] as String,
        nearestSite = j['nearest_disposal_site'] == null
            ? null
            : DisposalSite.fromJson(Map<String, dynamic>.from(j['nearest_disposal_site'] as Map));

  final int capacityUnits;
  final int loadUnits;
  final int reservedUnits;
  final int availableUnits;
  final double fillPercent;
  final String status;
  final DisposalSite? nearestSite;

  bool get needsDisposal => status == 'full' || status == 'nearly_full';
}
