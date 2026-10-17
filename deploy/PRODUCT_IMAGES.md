# Product image rollout

Each admin upload creates two JPEGs in `UPLOAD_FOLDER/products`: one detail image
(1200px max) and one thumbnail (600px max). The database still stores only the
detail URL. The client list API derives the thumbnail URL for new uploads and
leaves older or external URLs unchanged.

Production checks for `43.155.202.205`:

1. The Nginx vhosts in `deploy/fresh-produce.conf` and
   `deploy/fresh-produce-admin.conf` set `client_max_body_size 8m` for admin
   uploads. Test with `sudo nginx -t` before reloading. Flask also caps
   requests via `MAX_UPLOAD_MB` (8 MiB by default).
2. The default image directory lives under `/home/ubuntu`, which is not
   traversable by Nginx's `www-data` user. Production uses the dedicated
   `/srv/fresh-produce/uploads` directory configured in
   `deploy/fresh-produce.service`. Give `ubuntu` write and `www-data` read
   access. Both site configurations include a static image location:

   ```nginx
   location ^~ /uploads/products/ {
       alias /srv/fresh-produce/uploads/products/;
       expires 1y;
       access_log off;
   }
   ```

   Until this is configured, the existing Flask route can serve images.
3. Enable `fresh-produce-images-backup.timer` for a daily image archive under
   `backups/uploads`. The automatic GitHub deployment backs up MySQL only.
   Same-disk archives help with accidental deletion but not disk loss: enable
   cloud disk snapshots or separate storage. There is no automatic archive
   retention; monitor backup disk usage and set an approved retention policy.
4. After deployment, upload one non-sensitive image and verify both URLs,
   cache headers, the mini-program list thumbnail, detail image, and broken
   image placeholder on a real WeChat device.
5. GitHub deployment updates only the backend/admin panel. The mini-program
   still needs a new build uploaded in WeChat Developer Tools and published.
