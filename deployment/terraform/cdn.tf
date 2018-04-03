#
# CloudFront resources
#
resource "aws_cloudfront_distribution" "cdn" {
  origin {
    domain_name = "${aws_route53_record.origin.fqdn}"
    origin_id   = "originDistrictBuilder"

    custom_origin_config {
      http_port              = 8080
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1", "TLSv1.1", "TLSv1.2"]
    }
  }

  enabled          = true
  http_version     = "http2"
  comment          = "${var.project} (${var.environment})"
  retain_on_delete = true

  price_class = "${var.cdn_price_class}"
  aliases     = ["${lower(var.state)}.${replace(data.aws_route53_zone.external.name, "/.$/", "")}"]

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD", "OPTIONS"]
    target_origin_id = "originDistrictBuilder"

    forwarded_values {
      query_string = true
      headers      = ["*"]

      cookies {
        forward = "all"
      }
    }

    compress               = false
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 300
  }

  logging_config {
    include_cookies = false
    bucket          = "${data.terraform_remote_state.core.s3_log_bucket}.s3.amazonaws.com"
    prefix          = "${upper(var.state)}"
  }

  restrictions {
    geo_restriction {
      restriction_type = "whitelist"
      locations        = ["US"]
    }
  }

  viewer_certificate {
    acm_certificate_arn      = "${var.ssl_certificate_arn}"
    minimum_protocol_version = "TLSv1"
    ssl_support_method       = "sni-only"
  }

  tags {
    Project     = "${var.project}"
    Environment = "${var.environment}"
  }
}
