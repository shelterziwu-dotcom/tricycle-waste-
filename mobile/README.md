# TriCycle Waste mobile app

Flutter app for households and tricycle collectors. See "Running the mobile app" in the main
[README](../README.md) for setup, the server address to enter, and demo tips.

```
lib/
  api.dart              talks to the backend (HTTP, photo upload, live WebSocket events)
  session.dart          saved server address and login
  models.dart           pickups, rubber sizes, quotes, tricycle load, disposal sites
  location.dart         phone GPS
  widgets/common.dart   colours, status chips, load meter, rubber counter, photo picker, map helpers
  screens/
    server_screen.dart, login_screen.dart
    user/        user_home, book_pickup (rubbers + live price), pickup_detail (track, approve, pay, rate),
                 report_dumping
    collector/   collector_home (online, load meter, offers), job_screen (count rubbers + photo),
                 disposal_screen (geofenced check-in)
```
