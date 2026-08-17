<p align="center">
  <img src="custom_components/hanet_connect/brand/icon.png" alt="HANET Connect" width="128">
</p>

# HANET Connect cho Home Assistant

Custom integration giúp kết nối tài khoản và camera HANET với Home Assistant.
Đây là dự án cộng đồng, không phải sản phẩm chính thức của HANET.

## Yêu cầu

- Home Assistant `2025.1.0` trở lên.
- Tài khoản HANET đang xem được camera trên ứng dụng HANET Connect.
- URL máy chủ kích hoạt HTTPS và license key do đơn vị cung cấp bản cài gửi.
- Home Assistant có kết nối Internet để đăng nhập, kích hoạt và nhận dữ liệu.

## Cài đặt bằng HACS

1. Mở **HACS > Integrations**.
2. Mở menu góc trên bên phải, chọn **Custom repositories**.
3. Dán địa chỉ repository GitHub chứa integration này.
4. Chọn loại **Integration**, sau đó bấm **Add**.
5. Tìm **HANET Connect** trong HACS và chọn **Download**.
6. Khởi động lại Home Assistant.
7. Vào **Settings > Devices & services > Add integration**.
8. Tìm và chọn **HANET Connect**.

## Cài đặt thủ công

1. Tải source ZIP mới nhất của repository và giải nén.
2. Chép nguyên thư mục:

   ```text
   custom_components/hanet_connect
   ```

   vào thư mục cấu hình Home Assistant:

   ```text
   /config/custom_components/hanet_connect
   ```

3. Kiểm tra đường dẫn cuối cùng có dạng:

   ```text
   /config/custom_components/hanet_connect/manifest.json
   ```

4. Khởi động lại Home Assistant.
5. Vào **Settings > Devices & services > Add integration > HANET Connect**.

## Kích hoạt và đăng nhập

1. Nhập URL máy chủ kích hoạt HTTPS nếu ô này chưa được điền sẵn.
2. Nhập license key được cung cấp.
3. Nếu màn hình báo đang chờ duyệt, gửi **mã cài đặt** hiển thị trên màn hình
   cho đơn vị cấp license. Sau khi được duyệt, bấm gửi lại để tiếp tục.
4. Nhập tài khoản và mật khẩu HANET.
5. Chờ Home Assistant tải địa điểm, camera, FaceID và sự kiện.

Public signing key dùng để kiểm tra chữ ký license đã được nhúng sẵn trong
integration. Người dùng không cần tải, nhập hoặc chép thêm file sign key.

## Sử dụng

Sau khi cấu hình thành công, Home Assistant tự tạo các entity phù hợp với thiết
bị và quyền của tài khoản, bao gồm camera, ảnh nhận diện, cảm biến, sự kiện,
công tắc, nút bấm, lựa chọn và cập nhật firmware.

- Mở camera entity để xem ảnh hoặc luồng trực tiếp P2P.
- Mở trang thiết bị HANET để xem toàn bộ entity của từng camera.
- Sự kiện nhận diện mới được phát trên event bus với tên
  `hanet_connect_event`.
- Các action nâng cao nằm trong **Developer tools > Actions** với tiền tố
  `hanet_connect`.

Ví dụ lắng nghe sự kiện nhận diện:

```yaml
triggers:
  - trigger: event
    event_type: hanet_connect_event
actions:
  - action: persistent_notification.create
    data:
      title: HANET
      message: "{{ trigger.event.data }}"
```

Ví dụ gửi lệnh mở cửa:

```yaml
action: hanet_connect.send_command
data:
  device_id: "HANET_DEVICE_ID"
  command: open_door
```

Chỉ dùng các lệnh điều khiển với thiết bị mà bạn có quyền quản lý.

## Cập nhật

### Cài bằng HACS

1. Mở **HACS > Integrations > HANET Connect**.
2. Chọn bản cập nhật mới nhất.
3. Khởi động lại Home Assistant sau khi cập nhật.

### Cài thủ công

1. Tải source ZIP mới nhất.
2. Ghi đè thư mục `/config/custom_components/hanet_connect` bằng thư mục mới.
3. Khởi động lại Home Assistant.

Không xóa config entry trước khi cập nhật; cấu hình và entity hiện tại sẽ được
Home Assistant giữ lại.

## Xử lý sự cố

### Không tìm thấy integration

- Kiểm tra đúng đường dẫn
  `/config/custom_components/hanet_connect/manifest.json`.
- Xóa thư mục bị lồng hai lần như
  `custom_components/hanet_connect/hanet_connect`.
- Khởi động lại toàn bộ Home Assistant, không chỉ tải lại YAML.
- Làm mới trình duyệt nếu giao diện vẫn giữ cache cũ.

### Không kích hoạt được license

- Kiểm tra URL máy chủ bắt đầu bằng `https://` và không có khoảng trắng.
- Kiểm tra Home Assistant có Internet và ngày giờ hệ thống chính xác.
- Kiểm tra license key được nhập đầy đủ.
- Nếu license đang chờ duyệt, bị khóa, hết hạn hoặc đã đủ số máy, liên hệ đơn vị
  cấp license và gửi mã cài đặt đang hiển thị.

### Không đăng nhập được HANET

- Kiểm tra lại tài khoản và mật khẩu trên ứng dụng HANET Connect.
- Nếu vừa đổi mật khẩu, mở integration và chọn **Reconfigure** để nhập lại.
- Đảm bảo tài khoản đang được chia sẻ đúng địa điểm và camera cần sử dụng.

### Không thấy camera hoặc không xem được live

- Mở ứng dụng HANET Connect để kiểm tra camera vẫn online và tài khoản còn quyền.
- Chờ một phút rồi tải lại integration trong **Devices & services**.
- Đóng các phiên xem live cũ trước khi mở lại camera.
- Xem log Home Assistant và tìm từ khóa `hanet_connect` nếu lỗi tiếp tục xảy ra.

## Gỡ cài đặt

1. Vào **Settings > Devices & services > HANET Connect** và xóa config entry.
2. Gỡ integration trong HACS hoặc xóa thư mục
   `/config/custom_components/hanet_connect`.
3. Khởi động lại Home Assistant.

## Bảo mật và quyền riêng tư

- Không chia sẻ license key, mật khẩu HANET hoặc file backup Home Assistant.
- Chỉ cài repository và bản phát hành từ nguồn mà bạn tin cậy.
- Kiểm tra nội dung diagnostics trước khi đăng công khai.
- Chỉ sử dụng integration với tài khoản và thiết bị mà bạn có quyền truy cập.
