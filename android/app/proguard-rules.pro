# Moshi
-keep class eu.privatregnskap.app.data.network.dto.** { *; }
-keepclassmembers class eu.privatregnskap.app.data.network.dto.** { *; }

# Retrofit
-keepattributes Signature
-keepattributes Exceptions
-keep class retrofit2.** { *; }

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
