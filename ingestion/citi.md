## `station_status_log.csv`

| Kolom | Tipe | Deskripsi |
| --- | --- | --- |
| `polled_at` | timestamp | Waktu script melakukan request (UTC, ISO format). |
| `station_id` | string | ID unik stasiun. |
| `num_bikes_available` | int | Jumlah sepeda reguler siap disewa saat itu, yaitu inventory level utama. |
| `num_bikes_disabled` | int | Sepeda yang ada secara fisik tetapi rusak atau tidak bisa disewa. |
| `num_docks_available` | int | Slot kosong untuk parkir sepeda, sebagai proxy kapasitas yang tersisa. |
| `num_docks_disabled` | int | Slot rusak atau tidak bisa dipakai. |
| `num_ebikes_available` | int | Subset e-bike dari `num_bikes_available`. |
| `is_installed` | 0/1 | Apakah stasiun fisik terpasang. |
| `is_renting` | 0/1 | Apakah stasiun sedang menerima peminjaman. |
| `is_returning` | 0/1 | Apakah stasiun sedang menerima pengembalian. |
| `last_reported` | Unix timestamp | Waktu API atau sensor stasiun terakhir memperbarui data. Field ini dapat digunakan untuk deduplication. |

## `station_information.csv`

| Kolom | Tipe | Deskripsi |
| --- | --- | --- |
| `station_id` | string | ID unik stasiun dan key untuk join dengan `station_status_log.csv`. |
| `name` | string | Nama lokasi stasiun. |
| `lat`, `lon` | float | Koordinat geografis. |
| `capacity` | int | Total kapasitas stasiun. Secara umum, bikes + docks mendekati nilai ini. |
| `region_id` | string | ID wilayah atau borough, jika tersedia di sistem. |